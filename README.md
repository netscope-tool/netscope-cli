# NetScope - Network Diagnostics & Reporting Tool

A comprehensive CLI tool for network diagnostics, testing, and reporting.

## Features (Phase 1)

- ✅ Cross-platform OS detection (Linux, macOS, Windows)
- ✅ Automatic tool availability checking
- ✅ Ping connectivity tests
- ✅ Traceroute path analysis
- ✅ DNS resolution testing
- ✅ CSV logging with timestamps
- ✅ Structured logging to files
- ✅ Beautiful terminal output

## Getting started

### Prerequisites

- **Git** – to clone the repository  
- **Python 3.9+** – [python.org](https://www.python.org/downloads/) or your OS package manager  

### 1. Clone the repository

Clone the repo and go into the project directory. The folder name depends on how you cloned (e.g. `netscope-cli` if you cloned that repo).

```bash
git clone https://github.com/netscope-tool/netscope-cli.git
cd netscope-cli
```

**Important:** All following commands must be run from this project directory (the one that contains `setup.py`, `requirements.txt`, and the `netscope` folder).

### 2. Create and activate a virtual environment

Installing packages **system‑wide** can fail on macOS/Homebrew and some Linux setups with an `externally-managed-environment` error. Use a **virtual environment** in the project directory.

**macOS / Linux (Terminal, bash/zsh):**

```bash
# From the project directory (e.g. ~/.../netscope-cli)
python3 -m venv .venv
source .venv/bin/activate
```

**Windows – Command Prompt (cmd):**

```cmd
REM From the project directory (e.g. C:\Users\You\netscope-cli)
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows – PowerShell:**

```powershell
# From the project directory (e.g. C:\Users\You\netscope-cli)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` (or `.venv` on Windows) in your prompt. If you open a new terminal later, **go back into the project directory and activate the venv again** before running `netscope`.

### 3. Install dependencies and NetScope

With the virtual environment **activated** and from the **project directory**:

```bash
pip install -r requirements.txt
pip install -e .
```

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
netscope glossary           # list networking terms
netscope glossary latency   # definition of a term
```

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

## License

MIT License - See LICENSE file for details