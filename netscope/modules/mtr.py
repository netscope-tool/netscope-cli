"""MTR route-quality test with portable text report parsing."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from netscope.modules.base import BaseTest, TestResult

_HOST_RE = re.compile(r"^\s*(?P<hop>\d+)\.?\s*(?:\|--)?\s*(?P<host>\S+)")
_PERCENT_RE = re.compile(r"(?P<loss>\d+(?:\.\d+)?)%")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_mtr_report(text: str) -> List[Dict[str, Any]]:
    """Parse the stable wide report emitted by ``mtr --report --report-wide``.

    MTR versions differ in whether they print ``1.|--`` or ``1.`` before a
    hop. The parser tolerates both and preserves loss and RTT columns when
    present. It intentionally does not infer measurements for missing hops.
    """
    hops: List[Dict[str, Any]] = []
    for line in (text or "").splitlines():
        match = _HOST_RE.match(line)
        if not match:
            continue
        remainder = line[match.end():]
        loss_match = _PERCENT_RE.search(remainder)
        # Standard columns after host: Loss%, Snt, Last, Avg, Best, Wrst, StDev.
        tokens = remainder.split()
        loss = float(loss_match.group("loss")) if loss_match else None
        sent: Optional[int] = None
        rtts: List[float] = []
        if loss_match:
            try:
                idx = tokens.index(loss_match.group(0))
            except ValueError:
                idx = -1
            if idx >= 0:
                if idx + 1 < len(tokens) and tokens[idx + 1].isdigit():
                    sent = int(tokens[idx + 1])
                for token in tokens[idx + 2:idx + 7]:
                    if token in {"?", "???"}:
                        rtts.append(float("nan"))
                        continue
                    number = _NUMBER_RE.search(token)
                    if number:
                        rtts.append(float(number.group(0)))
        hop: Dict[str, Any] = {"hop": int(match.group("hop")), "host": match.group("host")}
        if loss is not None:
            hop["packet_loss_percent"] = loss
        if sent is not None:
            hop["sent"] = sent
        if rtts:
            names = ("last_ms", "avg_ms", "best_ms", "worst_ms", "stdev_ms")
            for name, value in zip(names, rtts):
                if value == value:  # omit unknown '?' RTTs (NaN)
                    hop[name] = value
        hops.append(hop)
    return hops


class MTRTest(BaseTest):
    """Run a finite MTR report and return per-hop loss and latency."""

    @staticmethod
    def build_command(target: str, cycles: int, executable: Optional[str] = None) -> List[str]:
        """Build a safe argument vector shared by one-shot and live sampling."""
        if not 1 <= cycles <= 100:
            raise ValueError("MTR cycles must be between 1 and 100")
        binary = executable or shutil.which("mtr")
        if not binary:
            raise FileNotFoundError("mtr is not installed or not found in PATH")
        return [
            binary, "--report", "--report-wide", "--report-cycles", str(cycles),
            "--no-dns", "--", target,
        ]

    def run(self, target: str, cycles: int = 10, timeout: Optional[int] = None) -> TestResult:
        started = datetime.now()
        if not 1 <= cycles <= 100:
            raise ValueError("MTR cycles must be between 1 and 100")
        executable = shutil.which("mtr")
        if not executable:
            return self._result(
                target, started, "failure", "mtr is not installed or not found in PATH.",
                error="Install mtr (for example: apt install mtr or brew install mtr).",
            )

        effective_timeout = timeout or max(20, cycles * 3 + 10)
        command = self.build_command(target, cycles, executable)
        try:
            proc = subprocess.run(
                command, capture_output=True, text=True, timeout=effective_timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return self.result_from_report(
                target, cycles, stdout, stderr, returncode=1, started=started,
                failure_summary=f"MTR did not finish within {effective_timeout}s.",
                failure_error=f"timeout after {effective_timeout}s",
            )
        except OSError as exc:
            return self._result(target, started, "failure", f"Could not start mtr: {exc}", error=str(exc))

        return self.result_from_report(
            target, cycles, proc.stdout or "", proc.stderr or "", proc.returncode, started=started,
        )

    def result_from_report(
        self,
        target: str,
        cycles: int,
        stdout: str,
        stderr: str = "",
        returncode: int = 0,
        started: Optional[datetime] = None,
        failure_summary: Optional[str] = None,
        failure_error: Optional[str] = None,
    ) -> TestResult:
        """Parse one completed report batch into the normal persisted result."""
        started = started or datetime.now()
        output = (stdout or "").strip()
        if stderr:
            output = f"{output}\n{stderr.strip()}".strip()
        hops = parse_mtr_report(stdout or "")
        status = "success" if returncode == 0 and hops else "failure"

        if failure_summary:
            summary = failure_summary
        elif returncode == 0 and not hops:
            summary = "MTR completed, but no hop rows could be parsed; see raw output."
        elif returncode != 0:
            summary = f"mtr exited with code {returncode}."
        else:
            end_to_end_loss = hops[-1].get("packet_loss_percent")
            average = hops[-1].get("avg_ms")
            details = []
            if end_to_end_loss is not None:
                details.append(f"{end_to_end_loss:g}% destination packet loss")
            if average is not None:
                details.append(f"{average:g} ms average RTT")
            suffix = f" ({', '.join(details)})" if details else ""
            summary = f"MTR observed {len(hops)} hop(s) over {cycles} cycle(s){suffix}."

        error = failure_error or (None if status == "success" else (stderr.strip() or f"mtr exited with code {returncode}"))
        return self._result(
            target, started, status, summary,
            metrics={
                "cycles": cycles,
                "hop_count": len(hops),
                "hop_details": hops,
                "interpretation_note": (
                    "Loss reported only at an intermediate hop can reflect ICMP rate limiting; "
                    "check whether it continues to later hops and the destination."
                ),
            },
            raw_output=output, error=error,
        )

    def parse_output(self, output: str) -> Dict[str, Any]:
        hops = parse_mtr_report(output)
        return {"hop_count": len(hops), "hop_details": hops}

    def _result(
        self,
        target: str,
        started: datetime,
        status: str,
        summary: str,
        metrics: Optional[Dict[str, Any]] = None,
        raw_output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> TestResult:
        result = TestResult(
            test_name="MTR Route Quality", target=target, status=status,
            timestamp=started, duration=(datetime.now() - started).total_seconds(),
            metrics=metrics or {}, summary=summary, raw_output=raw_output, error=error,
        )
        if self.csv_handler is not None:
            self._log_to_csv(result)
        return result

    def _log_to_csv(self, result: TestResult) -> None:
        for key, value in result.metrics.items():
            if key == "hop_details":
                continue
            self.csv_handler.write_result(
                timestamp=result.timestamp, test_name=result.test_name, target=result.target,
                metric=key, value=value, status=result.status, details=result.summary or "",
            )
        for hop in result.metrics.get("hop_details", []):
            self.csv_handler.write_result(
                timestamp=result.timestamp, test_name=result.test_name, target=result.target,
                metric=f"hop_{hop.get('hop')}", value=json.dumps(hop, sort_keys=True),
                status=result.status, details=result.summary or "",
            )
