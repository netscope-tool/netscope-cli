"""
Jupyter notebook generator for a single NetScope run directory.

Builds a simple `.ipynb` that:
  - Loads metadata.json and results.csv
  - Shows basic tables
  - Leaves space for further analysis
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from netscope.report.html_report import load_run_data


def _mk_markdown_cell(text: str) -> Dict[str, Any]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [text],
    }


def _mk_code_cell(code: str) -> Dict[str, Any]:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [code],
    }


def generate_notebook(run_dir: Path) -> Dict[str, Any]:
    """
    Generate a notebook JSON structure for a run directory.
    """
    run_dir = run_dir.resolve()
    data = load_run_data(run_dir)
    meta = data.get("metadata") or {}

    test_type = meta.get("test_type", "Unknown Test")
    target = meta.get("target", "—")
    status = meta.get("status", "—")
    timestamp = meta.get("timestamp", "")

    cells: List[Dict[str, Any]] = []

    # Title
    cells.append(
        _mk_markdown_cell(
            f"# NetScope Report – {test_type}\n\n"
            f"- **Target**: `{target}`\n"
            f"- **Status**: `{status}`\n"
            f"- **Timestamp**: `{timestamp}`\n"
        )
    )

    # Load metadata and CSV
    cells.append(
        _mk_code_cell(
            "from pathlib import Path\n"
            "import json\n"
            "import pandas as pd\n\n"
            f"run_dir = Path({json.dumps(str(run_dir))})\n"
            "meta_path = run_dir / 'metadata.json'\n"
            "csv_path = run_dir / 'results.csv'\n\n"
            "with meta_path.open('r', encoding='utf-8') as f:\n"
            "    metadata = json.load(f)\n"
            "display(metadata)\n\n"
            "df = pd.read_csv(csv_path)\n"
            "df.head()"
        )
    )

    # Group by test and show basic metrics
    cells.append(
        _mk_markdown_cell("## Metrics by test\n\n"
                          "This cell groups metrics by test name for quick inspection.")
    )
    cells.append(
        _mk_code_cell(
            "df.groupby(['test_name', 'metric'])['value'].first().unstack('metric')"
        )
    )

    # Placeholder for custom analysis
    cells.append(
        _mk_markdown_cell(
            "## Custom analysis\n\n"
            "- Plot latency over time\n"
            "- Filter by target or status\n"
            "- Join multiple runs, etc.\n"
        )
    )
    cells.append(
        _mk_code_cell(
            "# Example: filter metrics for Ping Test\n"
            "df_ping = df[df['test_name'] == 'Ping Test']\n"
            "df_ping"
        )
    )

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.x",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    return notebook


def generate_notebook_report(run_dir: Path, output_file: Path | None = None) -> Path:
    """
    Generate a Jupyter notebook for `run_dir`.

    Args:
        run_dir: Path to a single test run directory.
        output_file: Optional explicit output path. If None, writes
            `report.ipynb` inside the run directory.

    Returns:
        Path to the generated notebook file.
    """
    run_dir = run_dir.resolve()
    if output_file is None:
        output_file = run_dir / "report.ipynb"
    nb = generate_notebook(run_dir)
    output_file.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    return output_file

