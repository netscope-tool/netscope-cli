"""
Glossary content for `netscope glossary [term]`.
Each entry: (display_name, definition_text).
"""

GLOSSARY: dict[str, tuple[str, str]] = {
    "latency": (
        "Latency",
        "The time it takes for a packet to travel from source to destination and back (round-trip). "
        "Measured in milliseconds (ms).\n\n"
        "Rough guide: <20ms excellent, 20–50ms good, 50–100ms fair, >100ms poor.",
    ),
    "packet loss": (
        "Packet Loss",
        "The percentage of data packets that fail to reach their destination or to return. "
        "0% is ideal; any loss can cause lag, failed requests, or broken streams.",
    ),
    "ttl": (
        "TTL (Time To Live)",
        "A limit on how many hops a packet can take before being discarded. "
        "Prevents packets from looping forever. Each router decreases TTL by one.",
    ),
    "hop": (
        "Hop",
        "One step in the path between source and destination. Each router or gateway crossed counts as one hop. "
        "Traceroute shows the number of hops and the delay at each.",
    ),
    "dns": (
        "DNS (Domain Name System)",
        "The system that translates hostnames (e.g. google.com) into IP addresses. "
        "DNS lookup tests check that a name resolves correctly to one or more IPs.",
    ),
    "icmp": (
        "ICMP (Internet Control Message Protocol)",
        "Protocol used by ping. Many firewalls block ICMP, so 100% ping loss does not always mean the host is down.",
    ),
    "port": (
        "Port",
        "A number (1–65535) that identifies a service on a host. "
        "e.g. 80 (HTTP), 443 (HTTPS), 22 (SSH). Port scanning checks which ports are open.",
    ),
    "traceroute": (
        "Traceroute",
        "A test that shows the path of packets from your machine to a target, hop by hop, "
        "with round-trip time at each hop. Used to find where slowness or failure occurs.",
    ),
    "ping": (
        "Ping",
        "A test that sends ICMP echo requests to a host and measures whether it responds and the round-trip time (latency).",
    ),
    "resolve": (
        "Resolve / Resolution",
        "Translating a hostname to an IP address via DNS. "
        "'Resolved' means the DNS lookup returned at least one IP.",
    ),
}


def get_glossary_entry(term: str) -> tuple[str, str] | None:
    """Return (display_name, definition) for a term, or None. Matching is case-insensitive and by key."""
    key = term.strip().lower()
    if key in GLOSSARY:
        return GLOSSARY[key]
    # Allow partial key match (e.g. "packet" -> "packet loss")
    for k, v in GLOSSARY.items():
        if key in k or k.startswith(key):
            return v
    return None


def list_glossary_terms() -> list[str]:
    """Return sorted list of glossary keys (terms)."""
    return sorted(GLOSSARY.keys())
