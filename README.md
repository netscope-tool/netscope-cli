# NetScope - Network Diagnostics & Reporting Tool

[![PyPI version](https://badge.fury.io/py/netscope-cli.svg)](https://pypi.org/project/netscope-cli/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

A comprehensive CLI tool for network diagnostics, testing, and reporting.

## Install

**From PyPI (recommended):**

```bash
pip install netscope-cli
```

On many systems it’s better to use a virtual environment so you don’t install into the system Python. Create and activate one first, then install:

- **macOS / Linux (bash/zsh):**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install netscope-cli
  ```
- **Windows – Command Prompt:**
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate.bat
  pip install netscope-cli
  ```
- **Windows – PowerShell:**
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install netscope-cli
  ```

Optional features (nmap, speedtest, etc.):  
`pip install netscope-cli[security]` · `pip install netscope-cli[bandwidth]` · `pip install netscope-cli[all]`

## Features

- ✅ Cross-platform OS detection (Linux, macOS, Windows)
- ✅ Automatic tool availability checking
- ✅ Ping connectivity tests (with min/avg/max latency)
- ✅ Traceroute path analysis (with hop table)
- ✅ DNS resolution testing (IPv4/IPv6 aware)
- ✅ Pure-Python port scan (top ports) + optional nmap integration
- ✅ ARP scan and ping sweep for local discovery
- ✅ CSV logging with timestamps + structured logs
- ✅ HTML reports and Jupyter notebook reports per run
- ✅ Beautiful, educational terminal output (summaries, interpretations, glossary)

For a deeper guide, see:

- `docs/manual.md` – concepts, tests, interpreting results, reports.
- `docs/cli-reference.md` – full command and option reference.

## Development / install from source

Use this if you want to hack on the code or run tests.

### Prerequisites

- **Git** – to clone the repository  
- **Python 3.9+** – [python.org](https://www.python.org/downloads/) or your OS package manager  

### 1. Clone the repository

```bash
git clone https://github.com/netscope-tool/netscope-cli.git
cd netscope-cli
```

All following commands assume you are in this project directory (the one that contains `pyproject.toml`, `setup.py`, and the `netscope` folder).

### 2. Create and activate a virtual environment

Installing packages **system-wide** can fail on macOS/Homebrew and some Linux setups with an `externally-managed-environment` error. Use a **virtual environment** in the project directory.

**macOS / Linux (Terminal, bash/zsh):**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows – Command Prompt (cmd):**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows – PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` in your prompt. If you open a new terminal later, **cd into the project directory and activate the venv again** before running `netscope` or tests.

### 3. Install in editable mode

With the virtual environment **activated**:

```bash
pip install -r requirements.txt
pip install -e .
```

For development tools (pytest, black, ruff, etc.):  
`pip install -e ".[dev]"`

After this, the `netscope` command is available while the venv is active.

## Usage

### Interactive mode (menu-driven)

Run **`netscope`** with no arguments to start the interactive menu (or use **`netscope main`** for the same thing):

```bash
# From inside the virtual environment — starts the menu
netscope

# Same as above
netscope main

# Or using the Python module entry point
python -m netscope
```

You’ll see a header, system information, and then a menu where you can choose:

- Quick Network Check  
- Ping Test  
- Traceroute Test  
- DNS Lookup  
- Port Scan  
- Nmap Scan (if `nmap` is installed)  
- ARP Scan  
- Speedtest (optional; will prompt to install `speedtest-cli` if missing)  
- Ping Sweep  
- Exit

### Non-interactive mode (scripts / automation)

You can also run individual tests directly from the command line, which is useful for scripts, cron jobs, or quick one‑off checks:

```bash
# Ping test
netscope ping 8.8.8.8

# Traceroute test
netscope traceroute 8.8.8.8

# DNS lookup
netscope dns example.com

# Quick network check (ping + traceroute + DNS)
netscope quick-check example.com

# Pure-Python port scan (top ports)
netscope ports 192.168.1.1 --preset top100

# Nmap-based scan (if nmap is installed)
netscope nmap-scan example.com

# ARP scan (local devices)
netscope arp-scan

# Speedtest (download/upload; list servers: netscope speedtest --list)
netscope speedtest
netscope speedtest --server 12345

# Ping sweep over a small CIDR
netscope ping-sweep 192.168.1.0/24
```

By default, results are shown with the Rich TUI formatting.  
For machine‑readable output (e.g. piping to `jq` or logs), you can use:

```bash
netscope ping 8.8.8.8 --format json
netscope quick-check example.com --format json
```

### Help and learning

```bash
netscope --version          # or -V
netscope explain ping       # what the test does and how to interpret results
netscope explain traceroute
netscope explain quick-check
netscope glossary           # list networking terms
netscope glossary latency   # definition of a term
netscope history            # last 10 test runs (use -o to point to output dir)
netscope history -n 5       # last 5 runs
netscope examples           # common usage scenarios
netscope troubleshoot       # guided troubleshooting wizard
```

For a full command reference, see `docs/cli-reference.md`.

### Optional config file

You can set defaults in **`~/.netscope.yaml`** or **`.netscope.yaml`** in the current directory (optional; requires PyYAML):

```yaml
output_dir: ./my-output
verbose: false
timeout: 30
```

CLI options (e.g. `-o`, `-v`) override these values.

## Quick Start

1. Open a terminal, go to the project directory, and activate the venv (see [Getting started](#getting-started) above).
2. Run `netscope`
3. Select a test from the menu
4. Enter target host/IP (e.g. `8.8.8.8` or `google.com`)
5. View results in the terminal; detailed logs and CSV are in the `output/` directory

## Running tests

With the virtual environment activated and from the project directory:

```bash
pip install -r requirements.txt   # includes pytest
pytest tests/ -v
```

## Distribution

- **PyPI**: `pip install netscope-cli` (see [Install](#install) above)
- **Docker**: From the project root, `docker build -t netscope-cli .` then  
  `docker run --rm netscope-cli --version` or `docker run --rm -v $(pwd)/output:/data netscope-cli ping 8.8.8.8`
- **Homebrew**: A formula template is in `netscope.rb`; update the `sha256` and use  
  `brew install --build-from-source ./netscope.rb` or add to a tap. See [DISTRIBUTION_GUIDE.md](DISTRIBUTION_GUIDE.md).

Version is defined in `pyproject.toml`, `setup.py`, and optionally `netscope/__version__.py`; keep them in sync for releases.

## Requirements

### Linux
- `ping`, `traceroute`, `dig` (usually pre-installed)

### macOS
- `ping`, `traceroute`, `dig` (pre-installed)

### Windows
- `ping`, `tracert`, `nslookup` (pre-installed)

## Output Structure
```
output/
└── YYYY-MM-DD_HHMMSS_test_name/
    ├── metadata.json
    ├── results.csv
    ├── netscope.log
    └── raw_output/
```

## Contributing

We welcome contributions. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up your environment (including a virtual environment on your OS), run tests, and submit changes.

## Security

To report a security vulnerability, please see [SECURITY.md](SECURITY.md). Do not report security issues in the public issue tracker.

## License

MIT License – see [LICENSE](LICENSE) for details.