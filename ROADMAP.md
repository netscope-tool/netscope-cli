# NetScope – Project Status & Roadmap

## Bug fix (done)

- **`output_dir` validation error** – When running `netscope` without `-o`, Typer passed `None` and Pydantic rejected it. Fixed in `cli/main.py` by defaulting to `Path("output")` when `output_dir` is not provided.

---

## Phase 1 enhancements (improve what you have)

Small, high-impact improvements to the current MVP without new phases.

### Config & robustness

- **Config file support** – Optional `~/.netscope.yaml` or `./.netscope.yaml` for default `output_dir`, `timeout`, `verbose`, so `netscope` works without flags.
- **Resolve output path** – Use `config.output_dir.resolve()` so `output_dir` is always absolute and consistent (e.g. under `output/` from project root or CWD).
- **Graceful tool check** – If `dig` is missing on Windows, suggest `nslookup` and optionally use it in DNS test (with a note that output format differs).

### UX & CLI

- **Non-interactive mode** – Support `netscope ping 8.8.8.8` and `netscope quick-check example.com` for scripts/CI; skip menu and write to `output_dir`.
- **`--version`** – Typer/Click already support it if you set `version` on the app; ensure it prints e.g. `0.1.0`.
- **Target from args** – Allow `netscope -o ./out -- ping 8.8.8.8` or `netscope ping 8.8.8.8` so the target isn’t only from the interactive prompt.

### Output & formatting

- **Quick Network Check summary** – For “Quick Network Check”, show a single summary (e.g. table: Ping ✓/✗, Traceroute ✓/✗, DNS ✓/✗) instead of only the first result.
- **JSON output option** – `--format json` to print one JSON object per test (or one summary) for piping to jq/scripts.
- **Metrics in CSV** – Ensure all parsed metrics (min/avg/max latency, hop count, etc.) are columns in CSV, not only a subset.

### Parsing & metrics

- **Ping min/max** – Parse and store min/max latency (not only avg) from ping output; show in UI and CSV.
- **Traceroute per-hop table** – Parse hop-by-hop latency and show a small table (hop #, host, latency ms).
- **DNS A vs AAAA** – Record whether resolved addresses are IPv4 or IPv6 and show in summary.

### Code quality

- **`system_info.dict()`** – If you move to Pydantic v2, use `model_dump()` (and `model_dump(mode='json')` for serialization) instead of `.dict()`.
- **Tests** – A minimal pytest for `AppConfig` (default `output_dir`, `None` → `Path("output")`) and one test that runs executor with a mock command to lock in behavior.

---

## Phase 2: Enhanced testing (next)

### Port scanning & service discovery

| Item | Description | Effort |
|------|-------------|--------|
| **Nmap wrapper** | Optional dependency; subprocess call with `-sT`/`-sV`; parse stdout or `-oX -` XML. | M |
| **Nmap XML parser** | Extract hosts, ports (open/closed/filtered), service/version; optional OS guess. | M |
| **Basic port scanner** | Pure Python socket connect (e.g. 1–2s timeout) for when nmap isn’t installed; presets: “top 20”, “top 100”, custom list. | S |
| **Port scan test module** | Same interface as Ping/Traceroute/DNS: target + optional port list; result = open/closed list + CSV row. | S |

### Device discovery

| Item | Description | Effort |
|------|-------------|--------|
| **ARP scan** | Use `arp -a` (macOS/Windows) or `ip neigh`/`arp` (Linux); parse into “IP, MAC, interface”. | S |
| **OUI lookup** | Optional: map MAC prefix to vendor (embed or fetch small OUI list). | S |
| **Ping sweep** | Optional: asyncio or thread pool over a small CIDR (e.g. /24); “alive” list; respect timeout. | M |

### UI

| Item | Description | Effort |
|------|-------------|--------|
| **Progress bars** | Rich `Progress` for “Running ping…”, “Running traceroute…”, “Scanning ports…”. | S |
| **Live status** | Spinner or status line: “Pinging 8.8.8.8…” then “Done in 1.2s”. | S |
| **Summary dashboard** | After Quick Network Check: one panel with Pass/Fail per test and key metrics. | S |

### Parsing

| Item | Description | Effort |
|------|-------------|--------|
| **Traceroute hop table** | Parse each line into hop index, host, RTT; store in `TestResult.metrics` or new field. | S |
| **Ping stats** | Min/avg/max/mdev in metrics and CSV. | S |

**Phase 2 priority order (suggested):**

1. Basic port scanner + port scan test module (no nmap required).
2. Progress bars + live status.
3. Quick Network Check summary dashboard.
4. Nmap wrapper + XML parser (when nmap present).
5. ARP scan + optional OUI.
6. Ping sweep (optional, for small ranges).

---

## Phase 3: Reporting & visualization

### Reports

| Item | Description | Effort |
|------|-------------|--------|
| **HTML report** | Jinja2 template: header, system info, one section per test (tables + raw output); optional “Open in browser”. | M |
| **Charts** | Optional: latency over time (if multiple runs), port distribution; use Plotly or Chart.js (embedded). | M |
| **Jupyter notebook** | Generate `.ipynb` with markdown + code cells that load `metadata.json` and CSVs; pre-run cells for tables/plots. | M |
| **PDF** | Optional: from HTML (e.g. weasyprint) or ReportLab for formal reports. | L |

### Data

| Item | Description | Effort |
|------|-------------|--------|
| **Pandas in CLI** | Optional: `netscope summary output/` to aggregate CSVs and print stats (avg latency, success rate). | S |
| **Excel export** | Optional: `netscope export --excel output/` to write one sheet per test type or per run. | S |

**Phase 3 priority:** HTML report first (single run → one HTML file), then Jupyter template, then charts/PDF if needed.

---

## Phase 4: Advanced features

### Performance

| Item | Description | Effort |
|------|-------------|--------|
| **Async executor** | Run ping + traceroute + DNS in parallel for “Quick Network Check”; keep same result types. | M |
| **Parallel port scan** | Concurrent socket connects (e.g. asyncio or ThreadPool) with limit (e.g. 50). | S |

### History & comparison

| Item | Description | Effort |
|------|-------------|--------|
| **SQLite DB** | Optional: table per test type; store run id, timestamp, target, status, metrics (JSON); simple query API. | M |
| **Diff** | Compare two runs (e.g. two CSV or two DB rows): “New open ports”, “Ping latency +20%”, “DNS changed”. | M |

### Automation

| Item | Description | Effort |
|------|-------------|--------|
| **Cron-friendly** | Document `netscope quick-check 8.8.8.8 -o /var/netscope`; optional `--no-interactive` to exit 0/1 by result. | S |
| **Alerts** | Optional: if status != success or latency > threshold, run a script or send webhook (Slack/Discord). | M |

### Architecture

| Item | Description | Effort |
|------|-------------|--------|
| **YAML config** | As in Phase 1: defaults, timeouts, tool paths, output dir. | S |
| **Plugin hook** | Optional: “after_test” hook or registry of test classes so new tests (e.g. HTTP check) can be added without touching core. | L |

---

## Phase 5: Polish & distribution

### Quality

| Item | Description | Effort |
|------|-------------|--------|
| **Unit tests** | Config, parsers (ping/traceroute/DNS), formatters; mock executor. | M |
| **Integration test** | One “quick check” against 127.0.0.1 or a safe host; check exit code and that output dir is created. | S |
| **CI** | GitHub Actions: lint, pytest, optional matrix (Linux/macOS/Windows). | S |

### Distribution

| Item | Description | Effort |
|------|-------------|--------|
| **PyPI** | Publish `netscope-cli` or `netscope`; version in one place (e.g. `pyproject.toml` or `__init__.py`). | S |
| **Docker** | Image with `ping`, `traceroute`, `dig` (and optional nmap); entrypoint `netscope`. | S |
| **Homebrew** | Formula that `pip install` or uses a release tarball. | S |

### Documentation

| Item | Description | Effort |
|------|-------------|--------|
| **README** | Install (pip/venv), basic usage, `-o`, `--verbose`, non-interactive example. | S |
| **Docs** | Optional: MkDocs or Sphinx; CLI reference, config file, output layout. | M |

---

## Summary: what to do next

1. **Run the app** – Confirm `netscope` works after the `output_dir` fix.
2. **Phase 1 enhancements** – Add config file default for `output_dir`, then non-interactive subcommands and Quick Check summary.
3. **Phase 2** – Basic port scanner + progress bars, then nmap and ARP.
4. **Phase 3** – Single-run HTML report, then Jupyter and charts if needed.
5. **Phase 4–5** – Async, DB/diff, then tests + CI and PyPI/Docker/Homebrew.

Effort key: **S** = small (half day–1 day), **M** = medium (1–3 days), **L** = larger (3+ days).
