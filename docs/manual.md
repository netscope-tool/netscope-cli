# NetScope Manual

## Overview

NetScope is a CLI tool for network diagnostics, testing, and reporting. It wraps tools like
`ping`, `traceroute`/`tracert`, `dig`/`nslookup`, and optional `nmap`, and adds:

- Interactive menu with rich terminal output
- Structured results (CSV, logs, metadata)
- HTML reports and Jupyter notebooks
- Educational explainers, glossary, and troubleshooting wizard

Use this manual to understand what each test does, how to interpret the results, and how to
work with the generated reports.

## Core Concepts

- **Test run** – Each invocation of a NetScope test creates a timestamped directory under
  `output/`, containing:
  - `metadata.json` – summary of the run (type, target, status, system info, timestamp)
  - `results.csv` – metrics for the run
  - `netscope.log` – detailed logs
  - `raw_output/` – raw command output (when stored)
- **Target** – IP address or hostname. Smart shortcuts like `localhost`, `gateway`, and
  `dns` are resolved automatically.
- **Status** – `success`, `warning`, or `failure`. Warnings indicate partial issues
  (e.g. DNS returned no records, 100% packet loss).
- **Reports**:
  - HTML report (`report.html`) – visual summary of a single run.
  - Notebook report (`report.ipynb`) – Jupyter notebook for deeper analysis.

## Tests

### Ping Test

- **Command**: `netscope ping <target>`
- **What it does**: Sends ICMP echo requests to measure reachability and latency.
- **Key metrics** (also in CSV/HTML):
  - `packet_loss` – percentage of lost packets
  - `min_latency`, `avg_latency`, `max_latency` (ms)
  - `packets_received`
- **Interpretation**:
  - 0% loss and low latency → healthy connection.
  - Some loss or high latency → potential congestion or path issues.
  - 100% loss → host unreachable or blocking ICMP.

### Traceroute Test

- **Command**: `netscope traceroute <target>`
- **What it does**: Traces the path (hops) from your machine to the target.
- **Key metrics**:
  - `hop_count` – number of hops
  - `destination_reached` – whether final host responded
  - `hop_details` – per-hop RTT and host (shown in CLI/HTML, stored in metrics)

### DNS Lookup

- **Command**: `netscope dns <hostname>`
- **What it does**: Resolves a hostname to IP addresses using `dig` (Linux/macOS) or
  `nslookup` (Windows).
- **Key metrics**:
  - `ip_addresses` – list of resolved IPs
  - `ip_count`, `ipv4_count`, `ipv6_count`
  - `has_ipv4`, `has_ipv6`

### Quick Network Check

- **Command**: `netscope quick-check <target>`
- **What it does**: Runs Ping, Traceroute, and DNS together and summarizes results.
- **Output**:
  - Summary table with status and key metrics.
  - Plain-language interpretation panel.
  - CSV with metrics from all three tests.

### Port Scan (pure Python)

- **Command**: `netscope ports <target> [--preset top20|top100] [--format rich|json]`
- **What it does**: Uses TCP connect attempts to check if common ports are open.
- **Key metrics**:
  - `open_ports` (list)
  - `open_count`, `closed_count`, `total_ports`

### Nmap Scan (optional)

- **Command**: `netscope nmap-scan <target> [--ports ...]`
- **What it does**: Runs `nmap` with XML output and parses open ports and services.
- **Key metrics**:
  - `open_ports`, `open_count`, `closed_count`, `filtered_count`
  - `hosts_up`, `hosts_down`
  - `services` – per-port service details (name, product, version)

### ARP Scan

- **Command**: `netscope arp-scan`
- **What it does**: Reads the local ARP table to list devices on the local network.
- **Key metrics**:
  - `device_count`
  - `devices` – list with IP, MAC, interface, and vendor (OUI lookup)

### Ping Sweep

- **Command**: `netscope ping-sweep <CIDR>`
- **What it does**: Pings all hosts in a small CIDR (up to /24) to find which respond.
- **Key metrics**:
  - `alive_count`
  - `alive_hosts` – list of responding IPs
  - `total_addresses`

## Interpreting CLI Output

- **Status badge** – SUCCESS (green), WARNING (yellow), FAILURE (red).
- **Summary** – short explanation of what happened.
- **Metrics table** – key metrics; complex lists (e.g. hop details/devices) are shown in
  dedicated tables.
- **“What this means”** – plain-language interpretation per test.

## HTML Reports

- Generated with:
  - `netscope report-html <run_dir>` – HTML only.
  - `netscope report <run_dir>` – HTML + notebook (default).
- Contains:
  - Header with test, target, status, timestamp.
  - System information card.
  - “Tests by Status” chart (Chart.js).
  - One card per test with metrics.

## Notebook Reports

- Generated with:
  - `netscope report-notebook <run_dir>`
  - or as part of `netscope report <run_dir>`.
- Contents:
  - Loads `metadata.json` and `results.csv` into Python/pandas.
  - Shows raw tables and grouped metrics.
  - Includes example cells for filtering and custom analysis.

## Learning & Help

- `netscope explain <test>` – educational explanation of what a test does.
- `netscope glossary [term]` – definitions for networking terms.
- `netscope troubleshoot` – guided troubleshooting wizard.
- `netscope examples` – common usage scenarios.

