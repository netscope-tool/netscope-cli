# NetScope CLI Reference

This reference lists all `netscope` commands, their purpose, and short examples.  
For concepts, how each test works, and how to interpret results, see **docs/manual.md**.

## Top-level

```bash
netscope --help
netscope --version    # or -V
netscope main         # same as running netscope with no args
```

- **`netscope` / `netscope main`** – start the interactive menu.
- **`--version`** – print the current NetScope version.

## Core tests

### `netscope ping`

- **Description**: Ping a host and measure reachability/latency.
- **Usage**:
  ```bash
  netscope ping 8.8.8.8
  netscope ping google.com --format json
  netscope ping gateway       # smart shortcut
  ```

### `netscope traceroute`

- **Description**: Trace the path (hops) to a target.
- **Usage**:
  ```bash
  netscope traceroute 8.8.8.8
  netscope traceroute google.com --format json
  ```

### `netscope dns`

- **Description**: DNS lookup for a hostname (IPv4/IPv6 aware).
- **Usage**:
  ```bash
  netscope dns example.com
  netscope dns example.com --format json
  ```

### `netscope quick-check`

- **Description**: Run Ping, Traceroute, and DNS on the same target and summarize.
- **Usage**:
  ```bash
  netscope quick-check 8.8.8.8
  netscope quick-check example.com --format json
  ```

## Advanced tests

### `netscope ports`

- **Description**: Pure-Python port scan (TCP connect) on common ports.
- **Usage**:
  ```bash
  netscope ports 192.168.1.1
  netscope ports 192.168.1.1 --preset top100
  ```

### `netscope nmap-scan`

- **Description**: Nmap-based scan (requires `nmap` installed).
- **Usage**:
  ```bash
  netscope nmap-scan example.com
  netscope nmap-scan 192.168.1.1 --ports 22,80,443
  ```

### `netscope arp-scan`

- **Description**: List devices from the local ARP table.
- **Usage**:
  ```bash
  netscope arp-scan
  netscope arp-scan --format json
  ```

### `netscope ping-sweep`

- **Description**: Ping all hosts in a small CIDR (up to /24) to find which are alive.
- **Usage**:
  ```bash
  netscope ping-sweep 192.168.1.0/24
  netscope ping-sweep 10.0.0.0/24 --workers 100 --timeout 1.5
  ```

## Reports

### `netscope report`

- **Description**: Generate all reports (HTML and notebook) for a run directory.
- **Usage**:
  ```bash
  netscope report output/2026-02-13_115033_quick_network_check
  netscope report output/... --no-notebook   # HTML only
  netscope report output/... --no-html       # notebook only
  ```

### `netscope report-html`

- **Description**: Generate only the HTML report.
- **Usage**:
  ```bash
  netscope report-html output/2026-02-13_115033_quick_network_check
  ```

### `netscope report-notebook`

- **Description**: Generate only the Jupyter notebook report.
- **Usage**:
  ```bash
  netscope report-notebook output/2026-02-13_115033_quick_network_check
  ```

## Help & education

### `netscope explain`

- **Description**: Explain what a test does and how to interpret it.
- **Usage**:
  ```bash
  netscope explain ping
  netscope explain quick-check
  ```

### `netscope glossary`

- **Description**: Networking glossary.
- **Usage**:
  ```bash
  netscope glossary
  netscope glossary latency
  ```

### `netscope troubleshoot`

- **Description**: Interactive troubleshooting wizard.
- **Usage**:
  ```bash
  netscope troubleshoot
  ```

### `netscope examples`

- **Description**: Show common usage examples.
- **Usage**:
  ```bash
  netscope examples
  ```

### `netscope history`

- **Description**: Show recent runs from the output directory.
- **Usage**:
  ```bash
  netscope history
  netscope history -n 5 -o ./output
  ```

## Interactive menu

### `netscope main`

- **Description**: Start the interactive menu (same as `netscope`).
- **Usage**:
  ```bash
  netscope main
  ```

