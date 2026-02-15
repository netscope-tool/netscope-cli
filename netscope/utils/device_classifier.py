"""
Device classification and categorization based on various heuristics.
Classifies devices as servers, clients, IoT, network infrastructure, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DeviceCategory:
    """Device category classification."""
    
    primary: str  # server, client, iot, network, printer, mobile, unknown
    confidence: float  # 0.0 to 1.0
    indicators: List[str]  # List of indicators that led to this classification


def categorize_device(
    ip: str,
    mac: str,
    vendor: str,
    hostname: Optional[str] = None,
    open_ports: Optional[List[int]] = None,
) -> DeviceCategory:
    """
    Categorize a network device based on available information.
    
    Args:
        ip: IP address
        mac: MAC address
        vendor: Vendor name from MAC lookup
        hostname: Optional hostname
        open_ports: Optional list of open ports
        
    Returns:
        DeviceCategory with classification
    """
    indicators = []
    scores = {
        "server": 0.0,
        "client": 0.0,
        "iot": 0.0,
        "network": 0.0,
        "printer": 0.0,
        "mobile": 0.0,
    }
    
    # Vendor-based classification
    vendor_lower = vendor.lower()
    
    # Network infrastructure vendors
    network_vendors = [
        "cisco", "juniper", "aruba", "ubiquiti", "mikrotik", "netgear", 
        "tp-link", "d-link", "linksys", "asus router", "zyxel", "fortinet"
    ]
    for nv in network_vendors:
        if nv in vendor_lower:
            scores["network"] += 0.6
            indicators.append(f"Network vendor: {vendor}")
            break
    
    # Server/Enterprise vendors
    server_vendors = [
        "dell", "hp enterprise", "hpe", "supermicro", "lenovo server",
        "ibm", "oracle", "sun microsystems"
    ]
    for sv in server_vendors:
        if sv in vendor_lower:
            scores["server"] += 0.4
            indicators.append(f"Server vendor: {vendor}")
            break
    
    # IoT vendors
    iot_vendors = [
        "raspberry", "espressif", "arduino", "philips hue", "nest",
        "ring", "amazon", "google", "xiaomi", "tuya", "shelly",
        "sonoff", "wyze", "ecobee", "honeywell"
    ]
    for iv in iot_vendors:
        if iv in vendor_lower:
            scores["iot"] += 0.6
            indicators.append(f"IoT vendor: {vendor}")
            break
    
    # Printer vendors
    printer_vendors = [
        "canon", "epson", "brother", "xerox", "lexmark", "ricoh",
        "samsung printer", "kyocera"
    ]
    for pv in printer_vendors:
        if pv in vendor_lower:
            scores["printer"] += 0.7
            indicators.append(f"Printer vendor: {vendor}")
            break
    
    # Mobile device vendors
    mobile_vendors = [
        "apple", "samsung", "huawei", "xiaomi", "oppo", "vivo",
        "oneplus", "google pixel", "motorola", "lg electronics"
    ]
    for mv in mobile_vendors:
        if mv in vendor_lower:
            scores["mobile"] += 0.5
            indicators.append(f"Mobile vendor: {vendor}")
            break
    
    # Hostname-based classification
    if hostname:
        hostname_lower = hostname.lower()
        
        if any(x in hostname_lower for x in ["server", "srv", "db", "sql", "web", "api", "mail", "dns"]):
            scores["server"] += 0.5
            indicators.append(f"Server hostname pattern: {hostname}")
        
        if any(x in hostname_lower for x in ["router", "gateway", "switch", "ap", "firewall"]):
            scores["network"] += 0.5
            indicators.append(f"Network hostname pattern: {hostname}")
        
        if any(x in hostname_lower for x in ["printer", "print", "scanner"]):
            scores["printer"] += 0.5
            indicators.append(f"Printer hostname pattern: {hostname}")
        
        if any(x in hostname_lower for x in ["iphone", "ipad", "android", "mobile", "phone"]):
            scores["mobile"] += 0.5
            indicators.append(f"Mobile hostname pattern: {hostname}")
        
        if any(x in hostname_lower for x in ["iot", "sensor", "camera", "thermostat", "light", "bulb"]):
            scores["iot"] += 0.5
            indicators.append(f"IoT hostname pattern: {hostname}")
    
    # Port-based classification
    if open_ports:
        # Server ports
        server_ports = [
            80, 443, 8080, 8443,  # Web servers
            22, 3389,  # SSH, RDP
            3306, 5432, 27017, 6379,  # Databases
            25, 587, 465, 143, 993, 110, 995,  # Mail servers
            53,  # DNS server
            21, 20,  # FTP
        ]
        server_port_count = sum(1 for p in open_ports if p in server_ports)
        if server_port_count > 0:
            scores["server"] += min(server_port_count * 0.2, 0.6)
            indicators.append(f"{server_port_count} server port(s) open")
        
        # Network device ports
        network_ports = [23, 161, 162, 830, 22]  # Telnet, SNMP, NETCONF, SSH
        network_port_count = sum(1 for p in open_ports if p in network_ports)
        if network_port_count > 0:
            scores["network"] += min(network_port_count * 0.2, 0.5)
            indicators.append(f"{network_port_count} network management port(s) open")
        
        # Printer ports
        printer_ports = [9100, 515, 631]  # JetDirect, LPD, IPP
        printer_port_count = sum(1 for p in open_ports if p in printer_ports)
        if printer_port_count > 0:
            scores["printer"] += min(printer_port_count * 0.3, 0.7)
            indicators.append(f"{printer_port_count} printer port(s) open")
        
        # IoT typically has fewer open ports or specific ones
        if len(open_ports) <= 3 and any(p in [80, 443, 8080] for p in open_ports):
            scores["iot"] += 0.3
            indicators.append("Limited ports typical of IoT device")
    
    # IP-based heuristics
    # Gateway IPs often end in .1 or .254
    if ip.endswith(".1") or ip.endswith(".254"):
        scores["network"] += 0.3
        indicators.append(f"Gateway-like IP: {ip}")
    
    # Default classification if no strong indicators
    if max(scores.values()) < 0.3:
        scores["client"] = 0.5
        indicators.append("Default classification: client device")
    
    # Determine primary category
    primary = max(scores, key=scores.get)
    confidence = scores[primary]
    
    # Cap confidence at 1.0
    confidence = min(confidence, 1.0)
    
    return DeviceCategory(
        primary=primary,
        confidence=confidence,
        indicators=indicators,
    )


def get_category_icon(category: str) -> str:
    """Get icon/emoji for device category."""
    icons = {
        "server": "🖥️",
        "client": "💻",
        "iot": "🔌",
        "network": "🌐",
        "printer": "🖨️",
        "mobile": "📱",
        "unknown": "❓",
    }
    return icons.get(category, "❓")


def get_category_color(category: str) -> str:
    """Get Rich color for device category."""
    colors = {
        "server": "blue",
        "client": "green",
        "iot": "magenta",
        "network": "cyan",
        "printer": "yellow",
        "mobile": "bright_green",
        "unknown": "dim",
    }
    return colors.get(category, "white")


def get_category_description(category: str) -> str:
    """Get human-readable description for category."""
    descriptions = {
        "server": "Server/Service Host",
        "client": "Client Device",
        "iot": "IoT Device",
        "network": "Network Infrastructure",
        "printer": "Printer/Scanner",
        "mobile": "Mobile Device",
        "unknown": "Unknown Device",
    }
    return descriptions.get(category, "Unknown")
