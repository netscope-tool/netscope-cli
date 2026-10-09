"""Self-contained terminal-inspired HTML report generation."""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Dict, List


def load_run_data(run_dir: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {"metadata": {}, "rows": []}
    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        try:
            data["metadata"] = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data["metadata"] = {}
    csv_path = run_dir / "results.csv"
    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as stream:
                data["rows"] = list(csv.DictReader(stream))
        except (OSError, csv.Error):
            data["rows"] = []
    return data


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, (dict, list)):
                return json.dumps(decoded, ensure_ascii=False, indent=2, sort_keys=True)
        except (json.JSONDecodeError, TypeError):
            pass
    return str(value)


def _group_rows(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("test_name") or "Run metrics", []).append(row)
    return grouped


def _metric_table(rows: List[Dict[str, str]]) -> str:
    seen: Dict[str, str] = {}
    for row in rows:
        metric = row.get("metric")
        if metric:
            seen[metric] = row.get("value", "")
    if not seen:
        return '<p class="muted">No structured metrics were recorded.</p>'
    body = "".join(
        "<tr><th scope=\"row\">" + _escape(name.replace("_", " ").title())
        + "</th><td><pre>" + _escape(_display_value(value)) + "</pre></td></tr>"
        for name, value in seen.items()
    )
    return '<table><tbody>' + body + '</tbody></table>'


def _raw_evidence(run_dir: Path) -> str:
    raw_dir = run_dir / "raw_output"
    if not raw_dir.is_dir():
        return ""
    items = []
    for path in sorted(raw_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        was_truncated = len(content) > 200_000
        if was_truncated:
            content = content[:200_000] + "\\n\\n[Report preview truncated; see original evidence file.]"
        items.append(
            f'<details><summary>Raw evidence · {_escape(path.name)}</summary>'
            f'<pre>{_escape(content)}</pre></details>'
        )
    return (
        '<section class="block"><h2>Raw evidence</h2>' + "".join(items) + '</section>'
        if items else ""
    )


def generate_html(run_dir: Path) -> str:
    data = load_run_data(run_dir)
    metadata = data.get("metadata") or {}
    rows: List[Dict[str, str]] = data.get("rows") or []
    test_type = metadata.get("test_type", "Network test")
    target = metadata.get("target", "—")
    status = str(metadata.get("status", "unknown")).lower()
    timestamp = metadata.get("timestamp", "—")
    duration = metadata.get("duration_seconds")
    run_summary = next((row.get("details") for row in rows if row.get("details")), "")
    mode = metadata.get("scan_profile")
    cycles = metadata.get("cycles")
    ports = metadata.get("ports")
    timeout = metadata.get("timeout_seconds")
    status_class = status if status in {"success", "warning", "failure"} else "unknown"
    system_info = metadata.get("system_info") or {}
    grouped = _group_rows(rows)
    evidence = _raw_evidence(run_dir)

    mode_fact = f'<div><span class="label">PROFILE</span><code>{_escape(mode)}</code></div>' if mode else ""
    cycle_fact = f'<div><span class="label">CYCLES</span><code>{_escape(cycles)}</code></div>' if cycles is not None else ""
    ports_fact = f'<div><span class="label">PORTS</span><code>{_escape(ports)}</code></div>' if ports else ""
    timeout_fact = f'<div><span class="label">TIMEOUT</span><code>{_escape(timeout)}s</code></div>' if timeout is not None else ""
    summary = (
        f'<section class="summary"><div><span class="label">TARGET</span><code>{_escape(target)}</code></div>'
        f'<div><span class="label">STATUS</span><span class="status {status_class}">{_escape(status.upper())}</span></div>'
        f'<div><span class="label">DURATION</span><code>{_escape(f"{float(duration):.2f}s") if isinstance(duration, (int, float)) else "—"}</code></div>'
        f'{mode_fact}{cycle_fact}{ports_fact}{timeout_fact}<div><span class="label">RUN</span><code>{_escape(timestamp)}</code></div></section>'
    )
    narrative = (
        f'<section class="block"><h2>Run summary</h2><p>{_escape(run_summary)}</p></section>'
        if run_summary else ""
    )
    system_html = ""
    if isinstance(system_info, dict) and system_info:
        system_html = '<section class="block"><h2>Environment</h2><table><tbody>' + "".join(
            f'<tr><th scope="row">{_escape(key.replace("_", " ").title())}</th><td><pre>{_escape(_display_value(value))}</pre></td></tr>'
            for key, value in system_info.items()
        ) + '</tbody></table></section>'
    sections = "".join(
        f'<section class="block"><h2>{_escape(name)}</h2>{_metric_table(test_rows)}</section>'
        for name, test_rows in grouped.items()
    )
    if not sections:
        sections = '<section class="block"><p class="muted">No structured results are available for this run.</p></section>'

    css = """
:root{color-scheme:dark;--bg:#181715;--surface:#201f1c;--line:#3b3934;--text:#eeeae2;--muted:#aaa59a;--accent:#d97757;--green:#8db596;--yellow:#e2bd72;--red:#e27d72}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
main{max-width:1080px;margin:0 auto;padding:28px 24px 56px}header{border:1px solid var(--line);border-top:3px solid var(--accent);padding:20px 22px;background:var(--surface)}
.kicker,.label{color:var(--accent);font-size:11px;letter-spacing:.12em}h1{font-size:21px;font-weight:600;margin:8px 0 0}h2{font-size:14px;font-weight:600;margin:0 0 14px;color:var(--text)}
.summary{display:flex;gap:28px;flex-wrap:wrap;border:1px solid var(--line);border-top:0;padding:14px 20px;background:#1c1b18}.summary>div{display:flex;gap:10px;align-items:center}.status{font-weight:700}.status.success{color:var(--green)}.status.warning{color:var(--yellow)}.status.failure{color:var(--red)}.status.unknown{color:var(--muted)}
.block{margin-top:18px;border:1px solid var(--line);background:var(--surface);padding:18px 20px}table{width:100%;border-collapse:collapse}th,td{padding:9px 10px;border-top:1px solid var(--line);text-align:left;vertical-align:top}th{width:27%;font-weight:500;color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;color:var(--text);font:inherit}code{color:#f0b397;background:#171613;padding:2px 5px}.muted{color:var(--muted)}footer{margin-top:20px;color:var(--muted);font-size:11px}
@media(max-width:640px){main{padding:14px 10px 32px}.block{padding:14px 12px}.summary{gap:12px;flex-direction:column}th{width:35%}}
"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NetScope run report · {_escape(test_type)}</title><style>{css}</style></head>
<body><main><header><div class="kicker">NETSCOPE / RUN REPORT</div><h1>{_escape(test_type)}</h1></header>
{summary}{narrative}{system_html}{sections}{evidence}<footer>Generated from local NetScope run data · Raw evidence remains in this run directory.</footer></main></body></html>"""


def generate_html_report(run_dir: Path, output_file: Path | None = None) -> Path:
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise NotADirectoryError(run_dir)
    destination = output_file or run_dir / "report.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(generate_html(run_dir), encoding="utf-8")
    return destination
