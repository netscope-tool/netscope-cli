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
    """Parse the stable wide text report emitted by `mtr -r -w -n`.

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
                    if token == "?" or token == "???":
                        rtts.append(float("nan"))
                        continue
                    number = _NUMBER_RE.search(token)
                    if number:
                        rtts.append(float(number.group(0)))
        # If the loss column is absent, keep only the address and hop number.
        hop: Dict[str, Any] = {
            "hop": int(match.group("hop")),
            "host": match.group("host"),
        }
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

        # Each report cycle is approximately one second; a generous multiplier
        # leaves room for slow or partially unreachable routes.
        effective_timeout = timeout or max(20, cycles * 3 + 10)
        command = [
            executable, "--report", "--report-wide", "--report-cycles", str(cycles),
            "--no-dns", "--", target,
        ]
        try:
            proc = subprocess.run(
                command, capture_output=True, text=True, timeout=effective_timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            return self._result(
                target, started, "failure", f"MTR did not finish within {effective_timeout}s.",
                raw_output=output, error=f"timeout after {effective_timeout}s",
            )
        except OSError as exc:
            return self._result(target, started, "failure", f"Could not start mtr: {exc}", error=str(exc))

        output = (proc.stdout or "").strip()
        if proc.stderr:
            output = f"{output}\n{proc.stderr.strip()}".strip()
        hops = parse_mtr_report(proc.stdout or "")
        status = "success" if proc.returncode == 0 and hops else "failure"
        if proc.returncode == 0 and not hops:
            summary = "MTR completed, but no hop rows could be parsed; see raw output."
        elif proc.returncode != 0:
            summary = f"mtr exited with code {proc.returncode}."
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

        result = self._result(
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
            raw_output=output, error=None if status == "success" else (proc.stderr or None),
        )
        return result

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
