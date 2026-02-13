"""
MAC address vendor lookup utility.
Uses local OUI database for offline lookups.
"""

import json
import re
from pathlib import Path
from typing import Optional

# Embedded OUI database (top vendors for offline use)
OUI_DATABASE = {
    "00:00:0C": "Cisco Systems",
    "00:00:5E": "IANA (Reserved)",
    "00:01:42": "Cisco Systems",
    "00:01:43": "Cisco Systems",
    "00:03:47": "Intel Corporation",
    "00:04:5A": "Linksys",
    "00:05:02": "Apple Inc.",
    "00:0A:95": "Apple Inc.",
    "00:0C:29": "VMware Inc.",
    "00:0D:3A": "Microsoft Corporation",
    "00:0F:66": "Netgear Inc.",
    "00:11:24": "Apple Inc.",
    "00:13:72": "Dell Inc.",
    "00:14:22": "Dell Inc.",
    "00:15:5D": "Microsoft Corporation",
    "00:16:CB": "Apple Inc.",
    "00:17:F2": "Apple Inc.",
    "00:19:E3": "Apple Inc.",
    "00:1B:63": "Apple Inc.",
    "00:1C:42": "Apple Inc.",
    "00:1D:4F": "Apple Inc.",
    "00:1E:52": "Apple Inc.",
    "00:1F:5B": "Apple Inc.",
    "00:1F:F3": "Apple Inc.",
    "00:21:E9": "Dell Inc.",
    "00:22:41": "Apple Inc.",
    "00:23:12": "Apple Inc.",
    "00:23:32": "Apple Inc.",
    "00:23:6C": "Apple Inc.",
    "00:23:DF": "Apple Inc.",
    "00:24:36": "Apple Inc.",
    "00:25:00": "Apple Inc.",
    "00:25:4B": "Apple Inc.",
    "00:25:BC": "Apple Inc.",
    "00:26:08": "Apple Inc.",
    "00:26:4A": "Apple Inc.",
    "00:26:B0": "Apple Inc.",
    "00:26:BB": "Apple Inc.",
    "00:30:65": "Apple Inc.",
    "00:30:93": "Apple Inc.",
    "00:50:56": "VMware Inc.",
    "00:50:C2": "IEEE 802.1",
    "00:A0:C9": "Intel Corporation",
    "00:C0:CA": "Alfa Inc.",
    "00:D0:2D": "Cisco Systems",
    "00:E0:4C": "Realtek Semiconductor",
    "08:00:27": "Oracle VirtualBox",
    "08:00:2B": "Digital Equipment Corporation",
    "10:00:5A": "IBM Corp.",
    "10:40:F3": "Dell Inc.",
    "14:10:9F": "Ubiquiti Networks",
    "18:03:73": "Intel Corporation",
    "18:65:90": "Intel Corporation",
    "1C:1B:0D": "Giga-Byte Technology",
    "20:47:47": "TP-Link Corporation",
    "24:0A:64": "Espressif Inc.",
    "28:6A:BA": "D-Link Corporation",
    "2C:F0:5D": "Apple Inc.",
    "30:85:A9": "Apple Inc.",
    "34:15:9E": "Apple Inc.",
    "38:C9:86": "Apple Inc.",
    "3C:07:54": "Apple Inc.",
    "40:30:04": "Apple Inc.",
    "44:D9:E7": "Apple Inc.",
    "48:D7:05": "Apple Inc.",
    "4C:57:CA": "Apple Inc.",
    "50:32:37": "Apple Inc.",
    "54:26:96": "Apple Inc.",
    "54:E4:3A": "Apple Inc.",
    "58:55:CA": "Apple Inc.",
    "5C:95:AE": "Apple Inc.",
    "60:03:08": "Apple Inc.",
    "60:33:4B": "Apple Inc.",
    "60:69:44": "Apple Inc.",
    "60:F8:1D": "Apple Inc.",
    "64:20:0C": "Apple Inc.",
    "64:B9:E8": "Apple Inc.",
    "68:5B:35": "Apple Inc.",
    "68:96:7B": "Apple Inc.",
    "68:A8:6D": "Apple Inc.",
    "6C:40:08": "Apple Inc.",
    "6C:96:CF": "Apple Inc.",
    "70:11:24": "Apple Inc.",
    "70:56:81": "Apple Inc.",
    "70:CD:60": "Apple Inc.",
    "74:E1:B6": "Apple Inc.",
    "78:31:C1": "Apple Inc.",
    "78:67:D7": "Apple Inc.",
    "78:A3:E4": "Apple Inc.",
    "7C:11:BE": "Apple Inc.",
    "7C:6D:F8": "Apple Inc.",
    "80:49:71": "Apple Inc.",
    "80:E6:50": "Apple Inc.",
    "84:38:35": "Apple Inc.",
    "84:85:06": "Apple Inc.",
    "88:53:95": "Apple Inc.",
    "88:63:DF": "Apple Inc.",
    "88:E9:FE": "Apple Inc.",
    "8C:29:37": "Apple Inc.",
    "8C:85:90": "Apple Inc.",
    "90:27:E4": "Apple Inc.",
    "90:72:40": "Apple Inc.",
    "90:84:0D": "Apple Inc.",
    "94:E9:79": "Apple Inc.",
    "98:01:A7": "Apple Inc.",
    "98:D6:BB": "Apple Inc.",
    "9C:20:7B": "Apple Inc.",
    "9C:FC:E8": "Apple Inc.",
    "A0:99:9B": "Apple Inc.",
    "A4:5E:60": "Apple Inc.",
    "A4:83:E7": "Apple Inc.",
    "A4:D1:8C": "Apple Inc.",
    "A8:20:66": "Apple Inc.",
    "A8:5C:2C": "Apple Inc.",
    "A8:66:7F": "Apple Inc.",
    "A8:86:DD": "Apple Inc.",
    "AC:87:A3": "Apple Inc.",
    "AC:BC:32": "Apple Inc.",
    "AC:DE:48": "Apple Inc.",
    "B0:34:95": "Apple Inc.",
    "B0:65:BD": "Apple Inc.",
    "B4:18:D1": "Apple Inc.",
    "B4:F0:AB": "Apple Inc.",
    "B8:09:8A": "Apple Inc.",
    "B8:17:C2": "Apple Inc.",
    "B8:41:A4": "Apple Inc.",
    "B8:C7:5D": "Apple Inc.",
    "B8:E8:56": "Apple Inc.",
    "BC:3B:AF": "Apple Inc.",
    "BC:52:B7": "Apple Inc.",
    "BC:67:1C": "Apple Inc.",
    "BC:92:6B": "Apple Inc.",
    "C0:84:7D": "Apple Inc.",
    "C4:2C:03": "Apple Inc.",
    "C8:2A:14": "Apple Inc.",
    "C8:69:CD": "Apple Inc.",
    "C8:B5:B7": "Apple Inc.",
    "CC:08:8D": "Apple Inc.",
    "CC:25:EF": "Apple Inc.",
    "CC:29:F5": "Apple Inc.",
    "D0:03:4B": "Apple Inc.",
    "D0:25:98": "Apple Inc.",
    "D0:A6:37": "Apple Inc.",
    "D4:9A:20": "Apple Inc.",
    "D8:30:62": "Apple Inc.",
    "D8:96:95": "Apple Inc.",
    "DC:2B:61": "Apple Inc.",
    "DC:86:D8": "Apple Inc.",
    "DC:9B:9C": "Apple Inc.",
    "E0:33:8E": "Apple Inc.",
    "E0:AC:CB": "Apple Inc.",
    "E4:8B:7F": "Apple Inc.",
    "E4:CE:8F": "Apple Inc.",
    "E8:04:0B": "Apple Inc.",
    "E8:80:2E": "Apple Inc.",
    "EC:35:86": "Apple Inc.",
    "F0:18:98": "Apple Inc.",
    "F0:B4:79": "Apple Inc.",
    "F0:DB:E2": "Apple Inc.",
    "F4:0F:24": "Apple Inc.",
    "F4:1B:A1": "Apple Inc.",
    "F4:5C:89": "Apple Inc.",
    "F8:1E:DF": "Apple Inc.",
    "FC:25:3F": "Apple Inc.",
    "B4:2E:99": "Asustek Computer",
    "00:1A:92": "Asustek Computer",
    "00:22:15": "Asustek Computer",
    "00:24:8C": "Asustek Computer",
    "E0:CB:4E": "Asustek Computer",
    "F4:6D:04": "Asustek Computer",
    "00:24:D7": "Espressif Inc.",
    "30:AE:A4": "Espressif Inc.",
    "AC:67:B2": "Espressif Inc.",
    "B4:E6:2D": "Espressif Inc.",
    "CC:50:E3": "Espressif Inc.",
    "DC:4F:22": "Espressif Inc.",
    "00:1B:21": "Intel Corporation",
    "00:1E:67": "Intel Corporation",
    "00:21:6A": "Intel Corporation",
    "00:24:D6": "Intel Corporation",
    "00:27:0E": "Intel Corporation",
    "04:0E:3C": "Intel Corporation",
    "0C:8B:FD": "Intel Corporation",
    "34:02:86": "Intel Corporation",
    "3C:A9:F4": "Intel Corporation",
    "4C:34:88": "Intel Corporation",
    "7C:B2:7D": "Intel Corporation",
    "94:65:9C": "Intel Corporation",
    "A0:88:69": "Intel Corporation",
    "B4:96:91": "Intel Corporation",
    "D0:50:99": "Intel Corporation",
    "E4:B3:18": "Intel Corporation",
    "F0:DE:F1": "Intel Corporation",
    "00:14:BF": "Netgear Inc.",
    "00:18:4D": "Netgear Inc.",
    "00:1B:2F": "Netgear Inc.",
    "00:1E:2A": "Netgear Inc.",
    "00:24:B2": "Netgear Inc.",
    "00:26:F2": "Netgear Inc.",
    "08:BD:43": "Netgear Inc.",
    "20:E5:2A": "Netgear Inc.",
    "28:C6:8E": "Netgear Inc.",
    "2C:30:33": "Netgear Inc.",
    "A0:21:B7": "Netgear Inc.",
    "A0:63:91": "Netgear Inc.",
    "C0:3F:0E": "Netgear Inc.",
    "E0:46:9A": "Netgear Inc.",
    "00:0E:58": "TP-Link Corporation",
    "00:27:19": "TP-Link Corporation",
    "14:CF:92": "TP-Link Corporation",
    "50:C7:BF": "TP-Link Corporation",
    "54:A0:50": "TP-Link Corporation",
    "60:E3:27": "TP-Link Corporation",
    "84:16:F9": "TP-Link Corporation",
    "98:DE:D0": "TP-Link Corporation",
    "A4:2B:B0": "TP-Link Corporation",
    "C0:06:C3": "TP-Link Corporation",
    "E8:48:B8": "TP-Link Corporation",
    "F4:EC:38": "TP-Link Corporation",
}


def normalize_mac(mac: str) -> str:
    """
    Normalize MAC address to standard format (XX:XX:XX:XX:XX:XX).
    
    Args:
        mac: MAC address in various formats
        
    Returns:
        Normalized MAC address in uppercase with colons
    """
    # Remove common separators and whitespace
    mac_clean = re.sub(r'[:\-\.\s]', '', mac.upper())
    
    # Validate length
    if len(mac_clean) != 12:
        return mac  # Return original if invalid
    
    # Format as XX:XX:XX:XX:XX:XX
    return ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))


def get_oui(mac: str) -> str:
    """
    Extract OUI (Organizationally Unique Identifier) from MAC address.
    
    Args:
        mac: MAC address
        
    Returns:
        OUI (first 3 octets) in format XX:XX:XX
    """
    normalized = normalize_mac(mac)
    parts = normalized.split(':')
    if len(parts) >= 3:
        return ':'.join(parts[:3])
    return ""


def lookup_vendor(mac: str) -> Optional[str]:
    """
    Lookup vendor name from MAC address.
    
    Args:
        mac: MAC address in any common format
        
    Returns:
        Vendor name if found, None otherwise
    """
    oui = get_oui(mac)
    return OUI_DATABASE.get(oui)


def get_device_info(mac: str, ip: str = "", hostname: str = "") -> dict:
    """
    Get comprehensive device information.
    
    Args:
        mac: MAC address
        ip: IP address (optional)
        hostname: Hostname (optional)
        
    Returns:
        Dictionary with device information
    """
    vendor = lookup_vendor(mac)
    device_type = _guess_device_type(vendor, hostname)
    
    return {
        "mac": normalize_mac(mac),
        "ip": ip,
        "hostname": hostname,
        "vendor": vendor or "Unknown",
        "device_type": device_type,
        "oui": get_oui(mac),
    }


def _guess_device_type(vendor: Optional[str], hostname: str) -> str:
    """
    Guess device type based on vendor and hostname.
    
    Args:
        vendor: Vendor name
        hostname: Device hostname
        
    Returns:
        Guessed device type
    """
    if not vendor:
        return "Unknown"
    
    vendor_lower = vendor.lower()
    hostname_lower = hostname.lower() if hostname else ""
    
    # Network infrastructure
    if any(x in vendor_lower for x in ["cisco", "juniper", "arista", "mikrotik"]):
        return "Network Device"
    if any(x in vendor_lower for x in ["netgear", "tp-link", "linksys", "d-link", "asus"]):
        if any(x in hostname_lower for x in ["router", "gateway"]):
            return "Router"
        return "Router/AP"
    if "ubiquiti" in vendor_lower:
        return "Access Point"
    
    # Computers
    if any(x in vendor_lower for x in ["apple", "dell", "hp", "lenovo", "asus"]):
        if any(x in hostname_lower for x in ["iphone", "ipad"]):
            return "Mobile Device"
        if any(x in hostname_lower for x in ["macbook", "imac", "laptop"]):
            return "Computer"
        return "Computer/Device"
    
    # Virtualization
    if any(x in vendor_lower for x in ["vmware", "virtualbox", "qemu"]):
        return "Virtual Machine"
    
    # IoT
    if "espressif" in vendor_lower:
        return "IoT Device"
    if any(x in vendor_lower for x in ["raspberry", "arduino"]):
        return "IoT/Embedded"
    
    # Printers
    if any(x in vendor_lower for x in ["canon", "epson", "brother", "xerox"]):
        return "Printer"
    
    # Mobile
    if any(x in vendor_lower for x in ["samsung", "huawei", "xiaomi", "oppo"]):
        return "Mobile Device"
    
    # Intel NICs are common in servers and workstations
    if "intel" in vendor_lower:
        return "Computer/Server"
    
    return "Unknown"


def export_oui_database(output_path: Path) -> None:
    """
    Export the embedded OUI database to a JSON file.
    
    Args:
        output_path: Path to output JSON file
    """
    output_path.write_text(json.dumps(OUI_DATABASE, indent=2))


def import_oui_database(input_path: Path) -> dict:
    """
    Import OUI database from a JSON file.
    
    Args:
        input_path: Path to input JSON file
        
    Returns:
        Dictionary of OUI to vendor mappings
    """
    return json.loads(input_path.read_text())
