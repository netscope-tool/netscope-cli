"""
User-friendly CLI helpers for advanced test options.
Provides simple and expert modes for configuring tests.
"""

from typing import Optional
import questionary
from questionary import Choice

from netscope.modules.connectivity_enhanced import PingOptions
from netscope.modules.dns_enhanced import DNSOptions
from netscope.modules.ports_enhanced import PortScanOptions


def prompt_ping_options(simple_mode: bool = True) -> PingOptions:
    """
    Prompt user for ping test options.
    
    Args:
        simple_mode: If True, show simplified options; if False, show all options
        
    Returns:
        PingOptions configured by user
    """
    options = PingOptions()
    
    # Always ask for ping count
    count_choice = questionary.select(
        "How many pings to send?",
        choices=[
            Choice("4 (Quick)", value=4),
            Choice("10 (Standard)", value=10),
            Choice("20 (Detailed)", value=20),
            Choice("50 (Extensive)", value=50),
            Choice("100 (Stress test)", value=100),
            Choice("Custom", value="custom"),
        ],
        default="10 (Standard)"
    ).ask()
    
    if count_choice == "custom":
        count_str = questionary.text(
            "Enter number of pings (1-1000):",
            default="10",
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 1000
        ).ask()
        options.count = int(count_str)
    else:
        options.count = count_choice
    
    # Packet size / MTU testing
    packet_size_choice = questionary.select(
        "Packet size (for MTU testing)?",
        choices=[
            Choice("Default (56 bytes)", value=None),
            Choice("512 bytes", value=512),
            Choice("1024 bytes (1 KB)", value=1024),
            Choice("1472 bytes (Max for standard MTU)", value=1472),
            Choice("8192 bytes (8 KB)", value=8192),
            Choice("Custom", value="custom"),
        ],
        default="Default (56 bytes)"
    ).ask()
    
    if packet_size_choice == "custom":
        size_str = questionary.text(
            "Enter packet size in bytes (0-65507):",
            default="56",
            validate=lambda x: x.isdigit() and 0 <= int(x) <= 65507
        ).ask()
        options.packet_size = int(size_str)
    elif packet_size_choice is not None:
        options.packet_size = packet_size_choice
    
    if not simple_mode:
        # Advanced options
        
        # Interval
        interval_choice = questionary.select(
            "Interval between pings?",
            choices=[
                Choice("Default (1 second)", value=None),
                Choice("0.2 seconds (Fast)", value=0.2),
                Choice("0.5 seconds", value=0.5),
                Choice("2 seconds (Slow)", value=2.0),
                Choice("5 seconds (Very slow)", value=5.0),
            ],
            default="Default (1 second)"
        ).ask()
        options.interval = interval_choice
        
        # Timeout
        timeout_choice = questionary.select(
            "Timeout per ping?",
            choices=[
                Choice("Default (system)", value=None),
                Choice("1 second", value=1),
                Choice("2 seconds", value=2),
                Choice("5 seconds", value=5),
                Choice("10 seconds", value=10),
            ],
            default="Default (system)"
        ).ask()
        options.timeout = timeout_choice
        
        # TTL
        ttl_choice = questionary.confirm(
            "Set custom TTL (Time To Live)?",
            default=False
        ).ask()
        
        if ttl_choice:
            ttl_str = questionary.text(
                "Enter TTL (1-255):",
                default="64",
                validate=lambda x: x.isdigit() and 1 <= int(x) <= 255
            ).ask()
            options.ttl = int(ttl_str)
        
        # Don't fragment (for MTU discovery)
        if options.packet_size and options.packet_size > 1000:
            dont_fragment = questionary.confirm(
                "Enable 'Don't Fragment' flag? (Useful for MTU discovery)",
                default=True
            ).ask()
            options.dont_fragment = dont_fragment
    
    return options


def prompt_dns_options(simple_mode: bool = True) -> DNSOptions:
    """
    Prompt user for DNS query options.
    
    Args:
        simple_mode: If True, show simplified options; if False, show all options
        
    Returns:
        DNSOptions configured by user
    """
    options = DNSOptions()
    
    # Record type
    if simple_mode:
        record_choice = questionary.select(
            "DNS record type?",
            choices=[
                Choice("A (IPv4 address)", value="A"),
                Choice("AAAA (IPv6 address)", value="AAAA"),
                Choice("MX (Mail servers)", value="MX"),
                Choice("TXT (Text records)", value="TXT"),
                Choice("More types...", value="more"),
            ],
            default="A (IPv4 address)"
        ).ask()
        
        if record_choice == "more":
            record_choice = questionary.select(
                "Select DNS record type:",
                choices=[
                    Choice("NS (Name servers)", value="NS"),
                    Choice("CNAME (Canonical name)", value="CNAME"),
                    Choice("SOA (Start of authority)", value="SOA"),
                    Choice("PTR (Reverse lookup)", value="PTR"),
                    Choice("ANY (All records)", value="ANY"),
                ],
                default="NS (Name servers)"
            ).ask()
        
        options.record_type = record_choice
    else:
        # Expert mode - show all types
        record_choice = questionary.select(
            "DNS record type?",
            choices=[
                Choice("A (IPv4 address)", value="A"),
                Choice("AAAA (IPv6 address)", value="AAAA"),
                Choice("MX (Mail servers)", value="MX"),
                Choice("NS (Name servers)", value="NS"),
                Choice("TXT (Text records)", value="TXT"),
                Choice("CNAME (Canonical name)", value="CNAME"),
                Choice("SOA (Start of authority)", value="SOA"),
                Choice("PTR (Reverse lookup)", value="PTR"),
                Choice("SRV (Service records)", value="SRV"),
                Choice("ANY (All records)", value="ANY"),
            ],
            default="A (IPv4 address)"
        ).ask()
        options.record_type = record_choice
    
    # Custom DNS server
    if not simple_mode:
        use_custom_dns = questionary.confirm(
            "Use custom DNS server?",
            default=False
        ).ask()
        
        if use_custom_dns:
            dns_choice = questionary.select(
                "Select DNS server:",
                choices=[
                    Choice("Google (8.8.8.8)", value="8.8.8.8"),
                    Choice("Cloudflare (1.1.1.1)", value="1.1.1.1"),
                    Choice("Quad9 (9.9.9.9)", value="9.9.9.9"),
                    Choice("OpenDNS (208.67.222.222)", value="208.67.222.222"),
                    Choice("Custom IP", value="custom"),
                ],
                default="Google (8.8.8.8)"
            ).ask()
            
            if dns_choice == "custom":
                dns_server = questionary.text(
                    "Enter DNS server IP:",
                    validate=lambda x: len(x) > 0
                ).ask()
                options.dns_server = dns_server
            else:
                options.dns_server = dns_choice
        
        # Timeout
        timeout_choice = questionary.select(
            "Query timeout?",
            choices=[
                Choice("5 seconds (Default)", value=5),
                Choice("2 seconds (Fast)", value=2),
                Choice("10 seconds (Slow)", value=10),
                Choice("30 seconds (Very slow)", value=30),
            ],
            default="5 seconds (Default)"
        ).ask()
        options.timeout = timeout_choice
        
        # TCP
        use_tcp = questionary.confirm(
            "Use TCP instead of UDP?",
            default=False
        ).ask()
        options.tcp = use_tcp
        
        # DNSSEC
        use_dnssec = questionary.confirm(
            "Request DNSSEC validation?",
            default=False
        ).ask()
        options.dnssec = use_dnssec
    
    return options


def prompt_port_scan_options(simple_mode: bool = True) -> PortScanOptions:
    """
    Prompt user for port scan options.
    
    Args:
        simple_mode: If True, show simplified options; if False, show all options
        
    Returns:
        PortScanOptions configured by user
    """
    options = PortScanOptions()
    
    if simple_mode:
        # Simple mode - just timeout and service detection
        timeout_choice = questionary.select(
            "Connection timeout per port?",
            choices=[
                Choice("2 seconds (Default)", value=2.0),
                Choice("1 second (Fast)", value=1.0),
                Choice("5 seconds (Slow)", value=5.0),
            ],
            default="2 seconds (Default)"
        ).ask()
        options.timeout = timeout_choice
        
        service_detect = questionary.confirm(
            "Detect services on open ports? (Slower but more informative)",
            default=True
        ).ask()
        options.service_detection = service_detect
    
    else:
        # Expert mode - all options
        
        # Timeout
        timeout_choice = questionary.select(
            "Connection timeout per port?",
            choices=[
                Choice("0.5 seconds (Very fast)", value=0.5),
                Choice("1 second (Fast)", value=1.0),
                Choice("2 seconds (Default)", value=2.0),
                Choice("5 seconds (Slow)", value=5.0),
                Choice("10 seconds (Very slow)", value=10.0),
            ],
            default="2 seconds (Default)"
        ).ask()
        options.timeout = timeout_choice
        
        # Max workers
        workers_choice = questionary.select(
            "Concurrent threads?",
            choices=[
                Choice("32 (Conservative)", value=32),
                Choice("64 (Default)", value=64),
                Choice("128 (Aggressive)", value=128),
                Choice("256 (Very aggressive)", value=256),
            ],
            default="64 (Default)"
        ).ask()
        options.max_workers = workers_choice
        
        # Service detection
        service_detect = questionary.confirm(
            "Detect services on open ports?",
            default=True
        ).ask()
        options.service_detection = service_detect
        
        # UDP scanning
        scan_udp = questionary.confirm(
            "Also scan UDP ports? (Much slower)",
            default=False
        ).ask()
        options.scan_udp = scan_udp
        
        # Aggressive mode
        aggressive = questionary.confirm(
            "Use aggressive mode? (Faster but noisier)",
            default=False
        ).ask()
        options.aggressive = aggressive
    
    return options


def prompt_mode_selection() -> bool:
    """
    Ask user if they want simple or expert mode.
    
    Returns:
        True for simple mode, False for expert mode
    """
    mode = questionary.select(
        "Configuration mode:",
        choices=[
            Choice("🎯 Simple - Quick setup with common options", value="simple"),
            Choice("🔧 Expert - Full control over all parameters", value="expert"),
        ],
        default="🎯 Simple - Quick setup with common options"
    ).ask()
    
    return mode == "simple"
