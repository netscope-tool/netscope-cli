# Changelog

All notable changes to NetScope CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-13

### Added

#### Advanced Network Testing
- **Enhanced Device Discovery**: Comprehensive MAC vendor lookup with 200+ vendor database
- **Device Type Detection**: Automatic classification of network devices (routers, computers, IoT, etc.)
- **Bandwidth Testing**: Upload/download speed tests with multiple methods (HTTP, socket, speedtest-cli)
- **Jitter & Packet Loss Testing**: VoIP quality metrics for real-time communication assessment
- **Advanced ARP Scan**: Enhanced local network discovery with vendor and device type identification

#### Security Audit Features
- **SSL/TLS Security Analysis**: Certificate validation, cipher strength, protocol version checking
- **Port Security Audit**: Identification of dangerous open ports with risk assessment
- **DNS Security Testing**: DNSSEC validation, DNS leak detection, hijacking detection
- **Comprehensive Security Audit**: Unified security assessment with scoring (0-100) and risk levels
- **Security Recommendations**: Automated actionable recommendations based on findings

#### TUI/UX Enhancements
- **Real-time Dashboard**: Live network monitoring with metrics visualization
- **Enhanced Progress Indicators**: Detailed progress bars with ETA for long-running tests
- **Device Table**: Sortable, filterable table for discovered devices
- **Sparkline Graphs**: Inline trend visualization for metrics
- **ASCII Visualizations**: Terminal-based graphs, charts, and network topology diagrams
- **Color-coded Status**: Visual health indicators (green/yellow/red)
- **Minimalistic Design**: Clean, Anthropic-inspired terminal interface

#### Parallel Testing Infrastructure
- **Concurrent Test Execution**: Run tests on multiple targets simultaneously
- **Async Support**: Non-blocking I/O for improved performance
- **Rate Limiting**: Configurable concurrency and request rate controls
- **Batch Test Runner**: Execute multiple different tests in parallel
- **Continuous Monitoring**: Periodic testing with historical tracking
- **Resource Management**: Automatic cleanup and timeout handling

#### Reporting & Visualization
- **Interactive Visualizations**: Sparklines, bar charts, line graphs, heatmaps
- **Network Topology Diagrams**: ASCII art network maps
- **Enhanced Summary Panels**: Comprehensive test result summaries
- **Security Audit Reports**: Detailed security findings with severity levels

### Improved
- **MAC Vendor Lookup**: Expanded OUI database from ~50 to 200+ vendors
- **Error Handling**: Comprehensive edge case coverage
- **Code Organization**: New modular structure with tui/ and parallel/ directories
- **Type Safety**: Enhanced type hints throughout codebase

### Technical
- **New Modules**:
  - `netscope.utils.mac_vendor`: MAC address vendor identification
  - `netscope.modules.bandwidth`: Bandwidth and performance testing
  - `netscope.modules.security`: SSL/TLS, port, and DNS security
  - `netscope.modules.security_audit`: Comprehensive security auditing
  - `netscope.tui.dashboard`: Real-time monitoring dashboard
  - `netscope.tui.visualizations`: Terminal-based data visualization
  - `netscope.parallel.executor`: Parallel test execution engine

- **Dependencies**:
  - Core: typer, rich, questionary, pandas, loguru, pydantic
  - Optional: cryptography, python-nmap, speedtest-cli, scapy, netifaces, aiohttp

- **Distribution**:
  - Modern `pyproject.toml` configuration
  - PyPI-ready package structure
  - Comprehensive package metadata
  - Optional dependency groups (dev, security, bandwidth, advanced, all)

### Package Distribution
- **PyPI Ready**: Complete package configuration for `pip install netscope-cli`
- **Optional Dependencies**: Modular installation with feature-specific extras
- **Entry Points**: Global `netscope` command after installation
- **Cross-platform**: Windows, macOS, Linux support

### Documentation
- **Enhancement Design Document**: Comprehensive architecture and feature planning
- **Updated README**: Installation and usage instructions
- **Changelog**: Version tracking and release notes

## [0.1.0] - 2026-02-12

### Initial Release
- Basic ping, traceroute, DNS tests
- Port scanning (Python-based and nmap)
- ARP scan and ping sweep
- Interactive TUI with Rich
- CSV logging and HTML reports
- Educational features (explain, glossary)

[1.0.0]: https://github.com/netscope-tool/netscope-cli/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/netscope-tool/netscope-cli/releases/tag/v0.1.0
