# NetScope CLI - Distribution Guide

This guide provides comprehensive instructions for distributing NetScope CLI as a global Python package.

## Table of Contents

1. [Package Structure](#package-structure)
2. [Local Development Installation](#local-development-installation)
3. [Building Distribution Packages](#building-distribution-packages)
4. [Publishing to PyPI](#publishing-to-pypi)
5. [Platform-Specific Installers](#platform-specific-installers)
6. [Homebrew Formula](#homebrew-formula)
7. [Docker Distribution](#docker-distribution)
8. [Auto-Update Mechanism](#auto-update-mechanism)
9. [Version Management](#version-management)

---

## Package Structure

The package is configured using modern Python packaging standards:

```
netscope-cli/
├── pyproject.toml          # Modern package configuration
├── setup.py                # Legacy setup (for compatibility)
├── MANIFEST.in             # Package file inclusion rules
├── README.md               # Package description
├── CHANGELOG.md            # Version history
├── LICENSE                 # MIT License
├── requirements.txt        # Dependencies
├── netscope/              # Main package
│   ├── __init__.py
│   ├── __main__.py        # Entry point
│   ├── cli/               # CLI interface
│   ├── core/              # Core functionality
│   ├── modules/           # Test modules
│   ├── tui/               # TUI components
│   ├── parallel/          # Parallel execution
│   ├── utils/             # Utilities
│   ├── report/            # Reporting
│   └── storage/           # Data storage
└── tests/                 # Test suite
```

---

## Local Development Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package installer)
- git

### Installation Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/netscope-tool/netscope-cli.git
   cd netscope-cli
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in editable mode**:
   ```bash
   pip install -e .
   ```

4. **Install with optional dependencies**:
   ```bash
   # Security features
   pip install -e ".[security]"
   
   # Bandwidth testing
   pip install -e ".[bandwidth]"
   
   # Advanced features
   pip install -e ".[advanced]"
   
   # All features
   pip install -e ".[all]"
   
   # Development tools
   pip install -e ".[dev]"
   ```

5. **Verify installation**:
   ```bash
   netscope --version
   netscope --help
   ```

---

## Building Distribution Packages

### Install Build Tools

```bash
pip install build twine
```

### Build Source and Wheel Distributions

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build distributions
python -m build

# This creates:
# - dist/netscope_cli-1.0.0.tar.gz (source distribution)
# - dist/netscope_cli-1.0.0-py3-none-any.whl (wheel distribution)
```

### Verify Build

```bash
# Check package metadata
twine check dist/*

# Install from wheel to test
pip install dist/netscope_cli-1.0.0-py3-none-any.whl
```

---

## Publishing to PyPI

### Prerequisites

1. **Create PyPI account**: https://pypi.org/account/register/
2. **Create API token**: https://pypi.org/manage/account/token/
3. **Configure credentials**:
   ```bash
   # Create ~/.pypirc
   cat > ~/.pypirc << EOF
   [pypi]
   username = __token__
   password = pypi-YOUR-API-TOKEN-HERE
   EOF
   
   chmod 600 ~/.pypirc
   ```

### Test on TestPyPI (Recommended)

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ netscope-cli
```

### Publish to PyPI

```bash
# Upload to PyPI
twine upload dist/*

# Verify on PyPI
# Visit: https://pypi.org/project/netscope-cli/
```

### Post-Publication

Users can now install with:
```bash
pip install netscope-cli

# With optional features
pip install netscope-cli[all]
```

---

## Platform-Specific Installers

### Windows Installer (MSI)

Use PyInstaller to create standalone executable:

```bash
# Install PyInstaller
pip install pyinstaller

# Create Windows executable
pyinstaller --onefile \
    --name netscope \
    --add-data "netscope:netscope" \
    netscope/__main__.py

# Create MSI installer using WiX Toolset
# (Requires WiX Toolset: https://wixtoolset.org/)
```

### macOS Installer (DMG)

```bash
# Create macOS app bundle
pyinstaller --onefile \
    --name NetScope \
    --windowed \
    --add-data "netscope:netscope" \
    netscope/__main__.py

# Create DMG
# (Requires create-dmg: brew install create-dmg)
create-dmg \
    --volname "NetScope Installer" \
    --window-pos 200 120 \
    --window-size 800 400 \
    NetScope-1.0.0.dmg \
    dist/NetScope.app
```

### Linux Packages (DEB/RPM)

#### Debian/Ubuntu (DEB)

```bash
# Install packaging tools
sudo apt-get install dh-python python3-all debhelper

# Create debian package
# (Requires debian/ directory with control files)
dpkg-buildpackage -us -uc
```

#### RedHat/Fedora (RPM)

```bash
# Install packaging tools
sudo yum install rpm-build python3-devel

# Create RPM spec file and build
rpmbuild -ba netscope.spec
```

---

## Homebrew Formula

Create Homebrew formula for macOS/Linux installation:

### Create Formula

```ruby
# netscope.rb
class Netscope < Formula
  include Language::Python::Virtualenv

  desc "Comprehensive network diagnostics and security audit tool"
  homepage "https://github.com/netscope-tool/netscope-cli"
  url "https://files.pythonhosted.org/packages/source/n/netscope-cli/netscope-cli-1.0.0.tar.gz"
  sha256 "YOUR-SHA256-HASH-HERE"
  license "MIT"

  depends_on "python@3.11"

  resource "typer" do
    url "https://files.pythonhosted.org/packages/source/t/typer/typer-0.9.0.tar.gz"
    sha256 "..."
  end

  # Add other dependencies...

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/netscope", "--version"
  end
end
```

### Publish to Homebrew

```bash
# Create tap repository
brew tap-new yourusername/netscope

# Add formula
brew extract --version=1.0.0 netscope yourusername/netscope

# Users can install with:
# brew tap yourusername/netscope
# brew install netscope
```

---

## Docker Distribution

### Create Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    iputils-ping \
    traceroute \
    dnsutils \
    nmap \
    && rm -rf /var/lib/apt/lists/*

# Install netscope
RUN pip install --no-cache-dir netscope-cli[all]

# Set working directory
WORKDIR /data

# Entry point
ENTRYPOINT ["netscope"]
CMD ["--help"]
```

### Build and Publish

```bash
# Build image
docker build -t netscope/netscope-cli:1.0.0 .
docker tag netscope/netscope-cli:1.0.0 netscope/netscope-cli:latest

# Test locally
docker run --rm netscope/netscope-cli:latest --version

# Push to Docker Hub
docker login
docker push netscope/netscope-cli:1.0.0
docker push netscope/netscope-cli:latest

# Users can run with:
# docker run --rm netscope/netscope-cli ping 8.8.8.8
```

---

## Auto-Update Mechanism

### Version Checking

Add to `netscope/__init__.py`:

```python
import requests
from packaging import version

__version__ = "1.0.0"

def check_for_updates():
    """Check PyPI for newer version."""
    try:
        response = requests.get(
            "https://pypi.org/pypi/netscope-cli/json",
            timeout=2
        )
        latest = response.json()["info"]["version"]
        
        if version.parse(latest) > version.parse(__version__):
            print(f"New version available: {latest}")
            print("Update with: pip install --upgrade netscope-cli")
    except:
        pass  # Silently fail
```

### Auto-Update Command

Add CLI command:

```python
@app.command()
def update():
    """Update netscope to the latest version."""
    import subprocess
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "--upgrade", "netscope-cli"
    ])
```

---

## Version Management

### Semantic Versioning

Follow [SemVer](https://semver.org/):
- **MAJOR**: Breaking changes (2.0.0)
- **MINOR**: New features, backward compatible (1.1.0)
- **PATCH**: Bug fixes (1.0.1)

### Release Process

1. **Update version** in `pyproject.toml` and `netscope/__init__.py`
2. **Update CHANGELOG.md** with changes
3. **Commit changes**:
   ```bash
   git add .
   git commit -m "Release v1.0.0"
   git tag -a v1.0.0 -m "Version 1.0.0"
   git push origin main --tags
   ```
4. **Build and publish**:
   ```bash
   python -m build
   twine upload dist/*
   ```
5. **Create GitHub release** with changelog

### CI/CD Automation

Use GitHub Actions for automated releases:

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Build
        run: |
          pip install build twine
          python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

---

## Post-Distribution Checklist

- [ ] Package builds without errors
- [ ] All tests pass
- [ ] Documentation is up to date
- [ ] CHANGELOG is updated
- [ ] Version numbers are consistent
- [ ] PyPI package installs correctly
- [ ] Entry points work (`netscope` command)
- [ ] Optional dependencies install correctly
- [ ] README displays properly on PyPI
- [ ] GitHub release is created
- [ ] Docker image is published
- [ ] Homebrew formula is updated (if applicable)

---

## Support and Maintenance

### User Support
- GitHub Issues: https://github.com/netscope-tool/netscope-cli/issues
- Documentation: https://netscope-cli.readthedocs.io
- Email: support@netscope.dev

### Maintenance Schedule
- **Patch releases**: As needed for critical bugs
- **Minor releases**: Quarterly for new features
- **Major releases**: Annually for breaking changes

---

## Additional Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [PyPI Documentation](https://pypi.org/help/)
- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
