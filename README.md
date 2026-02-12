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

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/netscope.git
cd netscope
```

### 2. Create and activate a virtual environment

On recent macOS/Homebrew Python setups, trying to run `pip install -r requirements.txt` **system‑wide** can fail with an `externally-managed-environment` / PEP 668 error.  
The recommended and safest way is to use a **virtual environment** inside the project.

```bash
# Create a virtual environment in .venv/
python3 -m venv .venv

# Activate it (macOS / Linux)
source .venv/bin/activate

# On Windows (PowerShell)
# .venv\Scripts\Activate.ps1
```

You should now see `(.venv)` in your shell prompt.

### 3. Install dependencies and the package (development mode)

With the virtual environment **activated**:

```bash
# Install project dependencies
pip install -r requirements.txt

# Install netscope in editable / development mode
pip install -e .
```

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

## Quick Start

1. Run `netscope`
2. Select a test from the menu
3. Enter target host/IP
4. View results in terminal
5. Find detailed logs in `output/` directory

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