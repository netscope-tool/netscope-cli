"""
HTML report generator for a single NetScope run directory.

Given a run directory (with `metadata.json` and `results.csv`), this module
generates a self-contained `report.html` summarizing tests and key metrics.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def load_run_data(run_dir: Path) -> Dict[str, Any]:
    """
    Load metadata and CSV rows from a run directory.

    Returns a dict with:
      - metadata: dict from metadata.json (or {})
      - rows: list of CSV rows (each a dict)
    """
    data: Dict[str, Any] = {"metadata": {}, "rows": []}

    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        try:
            data["metadata"] = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            data["metadata"] = {}

    csv_path = run_dir / "results.csv"
    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                data["rows"] = list(reader)
        except Exception:
            data["rows"] = []

    return data


def _group_rows_by_test(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        test_name = row.get("test_name", "Unknown")
        grouped.setdefault(test_name, []).append(row)
    return grouped


def _escape(text: Any) -> str:
    """Basic HTML escaping."""
    s = str(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def generate_html(run_dir: Path) -> str:
    """
    Generate HTML string for a single run directory.
    """
    data = load_run_data(run_dir)
    meta = data.get("metadata") or {}
    rows: List[Dict[str, str]] = data.get("rows") or []

    test_type = meta.get("test_type", "Unknown Test")
    target = meta.get("target", "—")
    status = meta.get("status", "—")
    system_info = meta.get("system_info") or {}
    timestamp = meta.get("timestamp", "")

    grouped = _group_rows_by_test(rows)

    # Simple CSS for a clean report
    css = """
body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #0b1020; color: #f5f5f7; margin: 0; padding: 0; }
header { background: linear-gradient(90deg, #2563eb, #14b8a6); padding: 1.5rem 2rem; color: white; }
header h1 { margin: 0 0 0.3rem 0; font-size: 1.6rem; }
header p { margin: 0.1rem 0; opacity: 0.9; }
main { padding: 1.5rem 2rem 2rem 2rem; }
.card { background: #111827; border-radius: 0.75rem; padding: 1rem 1.2rem; margin-bottom: 1rem;
        border: 1px solid #1f2937; box-shadow: 0 10px 25px rgba(0,0,0,0.4); }
.badge { display: inline-block; padding: 0.1rem 0.6rem; border-radius: 999px; font-size: 0.75rem; }
.badge-success { background: #065f46; color: #bbf7d0; }
.badge-warning { background: #92400e; color: #fed7aa; }
.badge-failure { background: #7f1d1d; color: #fecaca; }
table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; font-size: 0.85rem; }
th, td { padding: 0.4rem 0.5rem; border-bottom: 1px solid #1f2937; text-align: left; }
th { color: #e5e7eb; font-weight: 600; }
tr:nth-child(even) { background: #020617; }
.section-title { font-size: 1.1rem; margin-bottom: 0.3rem; }
.muted { color: #9ca3af; font-size: 0.85rem; }
.pill { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px; background: #111827;
        border: 1px solid #1f2937; font-size: 0.75rem; margin-right: 0.25rem; color: #9ca3af; }
code { background: #020617; padding: 0.05rem 0.3rem; border-radius: 0.25rem; }
    """

    def status_badge(value: str) -> str:
        v = (value or "").lower()
        if v == "success":
            return '<span class="badge badge-success">SUCCESS</span>'
        if v == "warning":
            return '<span class="badge badge-warning">WARNING</span>'
        if v == "failure":
            return '<span class="badge badge-failure">FAILURE</span>'
        return f'<span class="badge">{_escape(value)}</span>'

    # Header HTML
    header_html = f"""
<header>
  <h1>NetScope Report</h1>
  <p><strong>Test:</strong> {_escape(test_type)}</p>
  <p><strong>Target:</strong> {_escape(target)} &nbsp; {status_badge(status)}</p>
  <p class="muted">{_escape(timestamp)}</p>
</header>
"""

    # System info card
    sys_rows = []
    if isinstance(system_info, dict) and system_info:
        for key, value in system_info.items():
            sys_rows.append(f"<div><span class='pill'>{_escape(key)}</span> {_escape(value)}</div>")
    sys_html = (
        "<div class='card'>"
        "<div class='section-title'>System Information</div>"
        + ("".join(sys_rows) if sys_rows else "<div class='muted'>No system information available.</div>")
        + "</div>"
    )

    # Per-test sections
    sections: List[str] = []
    for test_name, test_rows in grouped.items():
        # Collect key metrics (as last values per metric name)
        metrics: Dict[str, str] = {}
        for row in test_rows:
            metric = row.get("metric") or ""
            if metric:
                metrics[metric] = row.get("value", "")

        # Build a small metrics table (metric -> value)
        metrics_rows_html = ""
        if metrics:
            metrics_rows_html = "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>"
            for m_name, m_val in metrics.items():
                metrics_rows_html += (
                    f"<tr><td>{_escape(m_name.replace('_', ' ').title())}</td>"
                    f"<td>{_escape(m_val)}</td></tr>"
                )
            metrics_rows_html += "</tbody></table>"
        else:
            metrics_rows_html = "<div class='muted'>No metrics recorded for this test.</div>"

        sections.append(
            "<div class='card'>"
            f"<div class='section-title'>{_escape(test_name)}</div>"
            + metrics_rows_html
            + "</div>"
        )

    if not sections:
        sections.append(
            "<div class='card'><div class='muted'>No metrics were recorded for this run.</div></div>"
        )

    body_html = "<main>" + sys_html + "".join(sections) + "</main>"

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>NetScope Report - {_escape(test_type)}</title>
    <style>{css}</style>
  </head>
  <body>
    {header_html}
    {body_html}
  </body>
</html>
"""
    return html


def generate_html_report(run_dir: Path, output_file: Path | None = None) -> Path:
    """
    Generate an HTML report for `run_dir`.

    Args:
        run_dir: Path to a single test run directory.
        output_file: Optional explicit output HTML path. If None, writes `report.html`
            inside the run directory.

    Returns:
        Path to the generated HTML file.
    """
    run_dir = run_dir.resolve()
    if output_file is None:
        output_file = run_dir / "report.html"
    html = generate_html(run_dir)
    output_file.write_text(html, encoding="utf-8")
    return output_file

