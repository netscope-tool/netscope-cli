# NetScope terminal product direction

## Product shape

NetScope should be a guided terminal workspace first and a command-line tool second. The interactive entry point should make common jobs discoverable without requiring command syntax, while every action remains available as a reproducible command for scripts. The visual system should use quiet neutrals, a restrained clay accent, explicit state labels, and data tables rather than decoration. Do not use Anthropic or Claude logos; the intended reference is a warm, minimal visual tone.

Progress should report only what is known: current stage, target, elapsed time, completed work, and the next action. For tools that reveal results only when they exit (including common MTR report mode), use an honest activity indicator rather than an invented percentage. Long scans should show the exact selected mode and scope before execution, and preserve raw output beside parsed metrics.

## Capability map and gaps

Before this iteration, the codebase already included ping, traceroute, DNS, TCP port scanning, Nmap XML parsing, local ARP discovery, TLS checks, security-audit helpers, and HTML/notebook output. The largest gaps were that several capabilities were not surfaced in the guided flow, structured findings were inconsistently rendered, MTR and first-class website exploration were absent, and the HTML report had a separate visual identity and external chart dependency.

This iteration adds guided Nmap profile selection, a persistent alternate-screen MTR dashboard with finite `--once` support, an HTTP/TLS snapshot, passive certificate-transparency name discovery, and a recent-run picker for generating terminal-themed HTML reports without command syntax. CT results are explicitly treated as an inventory of public certificate observations; discovered hosts are not automatically contacted. The terminal result should identify coverage limitations (for example, unavailable CT lookup or an HTTP timeout) instead of presenting partial data as a clean bill of health.

Useful follow-on capabilities, ordered by user value and operational cost:

1. **Advanced scan profiles:** an explicitly opted-in vulnerability-script profile, saved scan presets, and user-tuned port lists. Keep scope, timing, and privilege requirements visible; do not silently run intrusive scripts.
2. **HTTP exploration:** redirect chain, DNS A/AAAA/CNAME, response timing, TLS chain/SANs, security headers, robots.txt/sitemap discovery, and a bounded crawl that stays on the requested origin.
3. **Path quality:** MTR trend capture, packet loss and jitter summaries, comparison against a prior run, and explicit identification of intermediate-hop loss that does not persist to the destination.
4. **History and change reports:** a lightweight SQLite index for run metadata, baselines, new/removed ports, certificate-expiry deltas, and DNS changes. Raw JSON/CSV should remain the portable source of truth.
5. **Extensibility:** a small test registry and reporter protocol so community checks can be added without growing a monolithic CLI module.

## Performance and packaging

Keep network probes in Python and use bounded concurrency for I/O. Avoid a rewrite until profiling identifies a hot path or deployment constraint that Python cannot meet. The current CLI does not use pandas; it is only imported inside notebook code generated for optional analysis, so it should not be a mandatory install dependency. Prefer standard-library TLS/HTTP/MTR wrappers, lazy imports for optional integrations, and small deterministic parsers. Benchmark cold start, memory use, and a fixed set of scans before considering Rust or a native extension.

## Reporting contract

Every run should retain metadata, raw command output when available, and structured measurements. Terminal, Markdown, and HTML outputs should share one hierarchy: target and scope; status and timing; concise finding summary; metric tables; detailed hop/service/certificate rows; limitations; and raw evidence. Findings should distinguish observation from interpretation and give the reader enough evidence to verify each recommendation.

## References

- [MTR manual](https://man.archlinux.org/man/mtr.8.en) documents finite report mode (`--report`), wide output, cycle count, and structured JSON/XML/CSV alternatives; flag availability can vary by installed version.
- [Nmap Reference Guide](https://nmap.org/book/man.html) describes host discovery, port states, service/version detection, and output formats. Scans should be limited to systems the operator is authorized to assess.
- [Python `ssl` documentation](https://docs.python.org/3/library/ssl.html) describes TLS contexts, peer certificate validation, and certificate metadata.
- [Textual](https://textual.textualize.io/) is a possible future event-driven widget framework. NetScope currently already depends on Rich; prefer a Rich-based first iteration until richer keyboard interaction justifies an additional runtime dependency.
- [crt.sh](https://crt.sh/) provides a public interface to Certificate Transparency search. Results may be incomplete, delayed, duplicated, or unavailable; they are not proof that a hostname is live.
