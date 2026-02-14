# Contributing to NetScope CLI

Thank you for considering contributing. This document explains how to set up your environment, run tests, and submit changes.

## Setting up your development environment

### Prerequisites

- **Python 3.9+** – [python.org](https://www.python.org/downloads/) or your OS package manager  
- **Git**

### 1. Clone the repository

```bash
git clone https://github.com/netscope-tool/netscope-cli.git
cd netscope-cli
```

### 2. Create and activate a virtual environment

Using a virtual environment keeps project dependencies separate from your system Python and avoids `externally-managed-environment` errors on many systems. **Use the commands for your OS and shell.**

#### macOS / Linux (bash or zsh)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows – Command Prompt (cmd)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

#### Windows – PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If you see `(.venv)` (or similar) in your prompt, the environment is active. When you open a new terminal, `cd` into the project directory and run the same **activate** command again.

### 3. Install the project in editable mode with dev dependencies

From the project root, with the virtual environment **activated**:

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

This installs the package in editable mode and adds pytest, black, ruff, mypy, etc. Optional extras:

```bash
pip install -e ".[dev,security,bandwidth]"   # for nmap/speedtest-related work
pip install -e ".[dev,all]"                  # everything
```

### 4. Verify the setup

```bash
netscope --version
netscope --help
pytest tests/ -v --tb=short
```

## Running tests

With the virtual environment activated and from the project root:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=netscope --cov-report=term-missing

# Run a single test file
pytest tests/test_connectivity.py -v
```

## Code style and linting

The project uses **Black** (formatting) and **Ruff** (linting). Config is in `pyproject.toml`.

- **Format code:**  
  `black netscope tests`

- **Lint:**  
  `ruff check netscope tests`

- **Type checking (optional):**  
  `mypy netscope`

Please run Black and Ruff before submitting a pull request so CI stays green.

## Submitting changes

1. **Fork** the repository (if you’re not a direct collaborator) and create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**, add or update tests as needed, and run:
   ```bash
   black netscope tests
   ruff check netscope tests
   pytest tests/ -v
   ```

3. **Commit** with clear messages (e.g. “Add speedtest server selection”, “Fix DNS timeout on Windows”).

4. **Push** your branch and open a **Pull Request** against `main`. Describe what you changed and why; reference any related issues.

5. **Address review feedback** if requested. Once approved, a maintainer will merge.

## Documentation

- **User-facing:** [README.md](README.md), [docs/manual.md](docs/manual.md), [docs/cli-reference.md](docs/cli-reference.md)  
- **Releases / packaging:** [DISTRIBUTION_GUIDE.md](DISTRIBUTION_GUIDE.md)  
- **Changelog:** [CHANGELOG.md](CHANGELOG.md) – add an entry for user-visible changes when you open a PR.

## Questions

Open a [GitHub Discussion](https://github.com/netscope-tool/netscope-cli/discussions) or an [Issue](https://github.com/netscope-tool/netscope-cli/issues) for questions. For security issues, use [SECURITY.md](SECURITY.md) instead.
