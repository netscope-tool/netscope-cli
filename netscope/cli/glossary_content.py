"""
Glossary content for `netscope glossary [term]`.
"""

GLOSSARY: dict[str, str] = {
    "latency": """
[bold]Latency[/bold] (also called "ping time" or "round-trip time")
  The time it takes for a packet to travel from your computer to a destination
  and back. Measured in milliseconds (ms).

[bold]What it means:[/bold]
  • Lower is better (faster response)
  • <20ms: Excellent (local network or very close)
  • 20–50ms: Good (same region)
  • 50–100ms: Fair (different region)
  • >100ms: Poor (distant or congested)

[bold]Example:[/bold]
  When you ping google.com and see "time=15ms", that's the latency.
""",
    "packet loss": """
[bold]Packet Loss[/bold]
  The percentage of packets that are sent but never received back.

[bold]What it means:[/bold]
  • 0%: Perfect (all packets returned)
  • 1–5%: Normal for some networks
  • >5%: Problematic (unstable connection)
  • 100%: Complete failure (host unreachable or blocking)

[bold]Causes:[/bold]
  • Network congestion
  • Faulty hardware
  • Firewall blocking packets
  • Host is down

[bold]Example:[/bold]
  "4 packets transmitted, 3 received, 25% packet loss" means 1 packet was lost.
""",
    "hop": """
[bold]Hop[/bold]
  A single router or gateway that a packet passes through on its way to
  the destination.

[bold]What it means:[/bold]
  • Each hop adds a small delay (latency)
  • More hops = longer path = potentially higher latency
  • Traceroute shows each hop with its IP address and delay

[bold]Example:[/bold]
  Your computer → Router (hop 1) → ISP gateway (hop 2) → Internet backbone (hop 3) → Destination
""",
    "ttl": """
[bold]TTL[/bold] (Time To Live)
  A counter in each packet that decreases by 1 at each hop. When it reaches 0,
  the packet is discarded.

[bold]What it means:[/bold]
  • Prevents packets from looping forever
  • Initial TTL is usually 64 (Linux/Mac) or 128 (Windows)
  • Traceroute uses TTL to discover each hop

[bold]Example:[/bold]
  A packet with TTL=1 reaches the first router, then is discarded. Traceroute
  uses this to map the path.
""",
    "dns": """
[bold]DNS[/bold] (Domain Name System)
  The system that translates human-readable hostnames (like google.com) into
  IP addresses (like 142.250.191.14).

[bold]What it means:[/bold]
  • Without DNS, you'd need to remember IP addresses
  • DNS servers store mappings of names to IPs
  • Your computer queries DNS servers to resolve names

[bold]Example:[/bold]
  When you type "google.com" in a browser, DNS resolves it to an IP address
  so your computer knows where to connect.
""",
    "ports": """
[bold]Port[/bold]
  A number (0–65535) that identifies which service or application should
  receive network traffic on a computer.

[bold]What it means:[/bold]
  • Port 80: HTTP (web traffic)
  • Port 443: HTTPS (secure web traffic)
  • Port 22: SSH (secure shell)
  • Port 25: SMTP (email)
  • Port scanning checks which ports are open (accepting connections)

[bold]Example:[/bold]
  When you visit a website, your browser connects to port 443 (HTTPS) on
  the server's IP address.
""",
    "ipv4": """
[bold]IPv4[/bold] (Internet Protocol version 4)
  The most common version of IP addresses, using 4 numbers separated by dots
  (e.g., 192.168.1.1).

[bold]What it means:[/bold]
  • Each number is 0–255 (32-bit address)
  • ~4.3 billion possible addresses (running out!)
  • Most networks still use IPv4

[bold]Example:[/bold]
  8.8.8.8 (Google DNS), 192.168.1.1 (common router IP)
""",
    "ipv6": """
[bold]IPv6[/bold] (Internet Protocol version 6)
  The newer version of IP addresses, using hexadecimal groups separated by colons
  (e.g., 2001:db8::1).

[bold]What it means:[/bold]
  • Much larger address space (128-bit)
  • Solves IPv4 address exhaustion
  • Not yet fully adopted everywhere
  • DNS can return both IPv4 (A record) and IPv6 (AAAA record)

[bold]Example:[/bold]
  2001:4860:4860::8888 (Google DNS IPv6), ::1 (localhost IPv6)
""",
    "gateway": """
[bold]Gateway[/bold]
  A router or device that connects your local network to another network
  (usually the internet).

[bold]What it means:[/bold]
  • Usually the first hop in traceroute
  • Often has IP like 192.168.1.1 or 10.0.0.1
  • Routes traffic between your network and the internet

[bold]Example:[/bold]
  Your home router is the gateway between your devices and the internet.
""",
    "icmp": """
[bold]ICMP[/bold] (Internet Control Message Protocol)
  A protocol used for diagnostic and error messages, including ping.

[bold]What it means:[/bold]
  • Ping uses ICMP echo requests/replies
  • Some networks block ICMP (so ping fails even if host is up)
  • Traceroute also uses ICMP (or UDP/TCP depending on OS)

[bold]Example:[/bold]
  When you ping a host, you're sending ICMP echo request packets.
""",
    "arp": """
[bold]ARP[/bold] (Address Resolution Protocol)
  Maps IP addresses to MAC (hardware) addresses on a local network.

[bold]What it means:[/bold]
  • Used only on local networks (LAN)
  • Each device has a MAC address (like a serial number)
  • ARP table shows which IPs map to which MACs

[bold]Example:[/bold]
  Your computer uses ARP to find the MAC address of your router when
  sending packets to it.
""",
    "mac": """
[bold]MAC Address[/bold] (Media Access Control)
  A unique hardware identifier for network interfaces, written as
  six pairs of hex digits (e.g., 00:1a:2b:3c:4d:5e).

[bold]What it means:[/bold]
  • Assigned by manufacturer (can identify vendor)
  • Used only on local networks (not routed over internet)
  • ARP maps IPs to MACs on LAN

[bold]Example:[/bold]
  Every network card has a MAC address that identifies it on the local network.
""",
}


def get_glossary_term(term: str) -> tuple[str, str] | None:
    """
    Return (term, content) for a glossary term, or None if not found.
    Term is normalized to lowercase.
    """
    key = term.strip().lower()
    if key not in GLOSSARY:
        return None
    return (term, GLOSSARY[key])


def list_all_terms() -> list[str]:
    """Return a sorted list of all glossary term names."""
    return sorted(GLOSSARY.keys())
