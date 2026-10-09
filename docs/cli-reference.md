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
  netscope nmap-scan 192.168.1.1 --profile connect
  netscope nmap-scan 192.168.1.1 --profile udp --ports 53,123
  ```
Profiles are `connect` (quick TCP inventory), `service` (light version detection; default), and `udp` (top 20 UDP ports unless `--ports` is supplied). Scan only systems you are authorized to assess.

### `netscope website-audit`

- **Description**: Check a site's TLS certificate, common HTTP security headers, and optionally discover hostnames from public Certificate Transparency records.
- **Usage**:
  ```bash
  netscope website-audit example.com
  netscope website-audit https://example.com --no-subdomains
  ```
Discovered CT names are passive certificate observations. NetScope does not probe those names automatically.

### `netscope mtr`

- **Description**: In a TTY, open the persistent full-screen route dashboard; the latest hop table refreshes in place until `q` or Ctrl+C. Non-interactive use runs one report.
- **Usage**:
  ```bash
  netscope mtr 8.8.8.8
  netscope mtr 8.8.8.8 --cycles 3       # refresh after each 3-cycle batch
  netscope mtr 8.8.8.8 --once --cycles 10
  netscope mtr 8.8.8.8 --once --format json
  ```
Requires the system `mtr` binary. The alternate-screen dashboard does not keep a scrollback of frames; it stores completed report batches with the run. Use `--once` for a single report or scripts.

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

From the interactive menu, choose **Generate HTML Report** to select a recent saved run and write `report.html` into its run directory.

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
