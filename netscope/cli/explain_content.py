"""
Educational content for `netscope explain <test>`.
"""

EXPLAIN_PING = """
[bold]What it does:[/bold]
  Sends ICMP echo packets to test if a host is reachable and measures
  round-trip time (latency).

[bold]When to use:[/bold]
  • Check if a website or server is online
  • Measure network latency
  • Verify internet connectivity
  • Diagnose connection issues

[bold]What the metrics mean:[/bold]
  • [cyan]Packet loss[/cyan]: % of packets that didn't return (0% = good)
  • [cyan]Latency (avg)[/cyan]: Time for packets to travel (lower = better)
    - <20ms: Excellent
    - 20–50ms: Good
    - 50–100ms: Fair
    - >100ms: Poor
  • [cyan]Max latency[/cyan]: Worst-case delay (spikes indicate issues)

[bold]Common issues:[/bold]
  • 100% loss: Host is down or blocking ICMP
  • High latency: Network congestion or distance
  • Variable latency: Unstable connection

[bold]Related tests:[/bold]
  • Traceroute: Find where slowness occurs
  • DNS: Check if hostname resolves correctly
"""

EXPLAIN_TRACEROUTE = """
[bold]What it does:[/bold]
  Shows the path packets take from your machine to the target, one hop
  (router) at a time, and the delay at each hop.

[bold]When to use:[/bold]
  • Find where network slowness or failure occurs
  • See the route to a host (which ISP/backbone)
  • Diagnose connectivity that works but is slow
  • Verify routing path

[bold]What the metrics mean:[/bold]
  • [cyan]Hop count[/cyan]: Number of routers crossed (more hops = longer path)
  • [cyan]Destination reached[/cyan]: Whether the final host responded
  • Each line: hop number, router IP/hostname, round-trip time(s)

[bold]Common issues:[/bold]
  • Timeouts at a hop: Router or link after it may be slow or blocking
  • Many hops: Normal for distant targets; high latency at one hop = bottleneck
  • Never reaches destination: Problem at or before the last responding hop

[bold]Related tests:[/bold]
  • Ping: Confirm host is reachable and measure end-to-end latency
  • DNS: Ensure hostname resolves before tracing
"""

EXPLAIN_DNS = """
[bold]What it does:[/bold]
  Resolves a hostname (e.g. google.com) to IP address(es) using DNS.
  Shows whether the name is valid and which server(s) it points to.

[bold]When to use:[/bold]
  • Check if a domain resolves correctly
  • See which IP(s) a hostname maps to
  • Diagnose "can't find website" issues
  • Verify DNS configuration

[bold]What the metrics mean:[/bold]
  • [cyan]Resolved[/cyan]: Whether at least one IP was returned
  • [cyan]IP count[/cyan]: Number of addresses (A/AAAA records)
  • Listed IPs: The actual addresses for the hostname

[bold]Common issues:[/bold]
  • No resolution: Typo in name, DNS server issue, or domain doesn't exist
  • Wrong IP: Caching or misconfiguration
  • Slow resolution: DNS server slow or network delay

[bold]Related tests:[/bold]
  • Ping: Test reachability of the resolved IP(s)
  • Traceroute: See path to the resolved IP
"""

EXPLAIN_PORTS = """
[bold]What it does:[/bold]
  Checks which TCP ports are open on a host by attempting a connection
  to each port (pure Python, no nmap required). Shows which ports
  accept connections and which do not.

[bold]When to use:[/bold]
  • Verify a service (web, SSH, etc.) is reachable
  • Quick check of common ports (top 20 or top 100)
  • Troubleshoot "service not responding"

[bold]What you get:[/bold]
  A list of open ports and counts. Presets: top 20 or top 100 common
  ports; you can also specify a custom port list.

[bold]Related tests:[/bold]
  • Ping: Check if the host is reachable first
  • Traceroute: See path to the host
"""

EXPLAIN_QUICK_CHECK = """
[bold]What it does:[/bold]
  Runs Ping, Traceroute, and DNS in sequence on the same target.
  Gives a quick overview of reachability, path, and name resolution.

[bold]When to use:[/bold]
  • First step when something is wrong (website down, slow, etc.)
  • Regular health check of a host
  • Compare all three views in one go

[bold]What you get:[/bold]
  A summary table with status and key metrics for each test.
  Use individual tests (ping, traceroute, dns) for full details.
"""

# Map CLI-friendly names to content
EXPLAIN_TOPICS: dict[str, str] = {
    "ping": EXPLAIN_PING,
    "traceroute": EXPLAIN_TRACEROUTE,
    "tracert": EXPLAIN_TRACEROUTE,
    "dns": EXPLAIN_DNS,
    "dig": EXPLAIN_DNS,
    "nslookup": EXPLAIN_DNS,
    "ports": EXPLAIN_PORTS,
    "port": EXPLAIN_PORTS,
    "quick-check": EXPLAIN_QUICK_CHECK,
    "quick": EXPLAIN_QUICK_CHECK,
}

# Display names for panel titles
EXPLAIN_TITLES: dict[str, str] = {
    "ping": "Ping Test",
    "traceroute": "Traceroute Test",
    "tracert": "Traceroute Test",
    "dns": "DNS Lookup",
    "dig": "DNS Lookup",
    "nslookup": "DNS Lookup",
    "ports": "Port Scan",
    "port": "Port Scan",
    "quick-check": "Quick Network Check",
    "quick": "Quick Network Check",
}


def get_explain_content(topic: str) -> tuple[str, str] | None:
    """
    Return (title, content) for a topic, or None if not found.
    Topic is normalized to lowercase; aliases (tracert, dig, etc.) are supported.
    """
    key = topic.strip().lower().replace(" ", "-")
    if key not in EXPLAIN_TOPICS:
        return None
    title = EXPLAIN_TITLES.get(key, topic)
    content = EXPLAIN_TOPICS[key]
    return (title, content)
