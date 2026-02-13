"""
ARP scan: discover devices on local network using ARP table.
"""

import platform
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from netscope.modules.base import BaseTest, TestResult

# Common OUI prefixes (first 3 bytes of MAC address) mapped to vendor names
# This is a small subset; full OUI database would be much larger
OUI_DATABASE: Dict[str, str] = {
    "00:1a:2b": "Cisco",
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "00:05:69": "VMware",
    "08:00:27": "VirtualBox",
    "00:15:5d": "Microsoft",
    "00:1e:67": "Apple",
    "00:23:df": "Apple",
    "00:25:00": "Apple",
    "00:25:4b": "Apple",
    "00:26:08": "Apple",
    "00:26:4a": "Apple",
    "00:26:bb": "Apple",
    "00:26:ca": "Apple",
    "00:50:56": "VMware",
    "00:0d:3a": "Dell",
    "00:14:22": "Dell",
    "00:21:70": "Dell",
    "00:24:e8": "Dell",
    "00:1b:21": "Dell",
    "00:1e:c2": "Dell",
    "00:25:64": "Dell",
    "00:26:b9": "Dell",
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "00:05:69": "VMware",
    "00:1c:14": "Hewlett-Packard",
    "00:1e:0b": "Hewlett-Packard",
    "00:21:5a": "Hewlett-Packard",
    "00:23:7d": "Hewlett-Packard",
    "00:25:b3": "Hewlett-Packard",
    "00:26:55": "Hewlett-Packard",
    "00:1d:72": "Samsung",
    "00:23:39": "Samsung",
    "00:26:5e": "Samsung",
    "00:16:32": "Intel",
    "00:1b:21": "Intel",
    "00:1e:67": "Intel",
    "00:21:5a": "Intel",
    "00:23:14": "Intel",
    "00:25:00": "Intel",
    "00:26:55": "Intel",
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "00:05:69": "VMware",
    "00:1a:79": "Google",
    "00:1e:c2": "Google",
    "00:23:6c": "Google",
    "00:26:bb": "Google",
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "00:05:69": "VMware",
    "00:1e:67": "Apple",
    "00:23:df": "Apple",
    "00:25:00": "Apple",
    "00:25:4b": "Apple",
    "00:26:08": "Apple",
    "00:26:4a": "Apple",
    "00:26:bb": "Apple",
    "00:26:ca": "Apple",
    "ac:de:48": "Apple",
    "f0:18:98": "Apple",
    "f4:f5:e8": "Apple",
    "f8:1e:df": "Apple",
    "fc:25:3f": "Apple",
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "00:05:69": "VMware",
}


def lookup_oui(mac: str) -> Optional[str]:
    """
    Look up vendor name from MAC address OUI (first 3 bytes).
    
    Args:
        mac: MAC address in format "XX:XX:XX:XX:XX:XX" or "XX-XX-XX-XX-XX-XX"
        
    Returns:
        Vendor name if found, None otherwise
    """
    # Normalize MAC address
    mac = mac.upper().replace("-", ":")
    parts = mac.split(":")
    if len(parts) < 3:
        return None
    
    oui = ":".join(parts[:3])
    return OUI_DATABASE.get(oui)


def parse_arp_output(output: str, os_type: str) -> List[Dict[str, Any]]:
    """
    Parse ARP table output into list of devices.
    
    Returns:
        List of dicts with keys: ip, mac, interface (optional), vendor (optional)
    """
    devices: List[Dict[str, Any]] = []
    
    if os_type == "Windows":
        # Windows: " 192.168.1.1           00-11-22-33-44-55     dynamic"
        pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\w+)')
        for line in output.split('\n'):
            match = pattern.search(line)
            if match:
                ip = match.group(1)
                mac = match.group(2).upper()
                interface = match.group(3) if len(match.groups()) > 2 else None
                vendor = lookup_oui(mac)
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": interface,
                    "vendor": vendor,
                })
    else:
        # Linux/macOS: "? (192.168.1.1) at 00:11:22:33:44:55 on en0"
        # or Linux: "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55"
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # macOS style: "? (192.168.1.1) at 00:11:22:33:44:55 on en0"
            macos_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]{17})', line)
            if macos_match:
                ip = macos_match.group(1)
                mac = macos_match.group(2).upper()
                interface_match = re.search(r'on\s+(\S+)', line)
                interface = interface_match.group(1) if interface_match else None
                vendor = lookup_oui(mac)
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": interface,
                    "vendor": vendor,
                })
                continue
            
            # Linux ip neigh style: "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55"
            linux_match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+dev\s+(\S+)\s+lladdr\s+([0-9a-fA-F:]{17})', line)
            if linux_match:
                ip = linux_match.group(1)
                interface = linux_match.group(2)
                mac = linux_match.group(3).upper()
                vendor = lookup_oui(mac)
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": interface,
                    "vendor": vendor,
                })
                continue
            
            # Fallback: try to find IP and MAC anywhere in line
            ip_match = re.search(r'\b(\d+\.\d+\.\d+\.\d+)\b', line)
            mac_match = re.search(r'\b([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})\b', line)
            if ip_match and mac_match:
                ip = ip_match.group(1)
                mac = mac_match.group(1).upper()
                vendor = lookup_oui(mac)
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": None,
                    "vendor": vendor,
                })
    
    return devices


class ARPScanTest(BaseTest):
    """ARP table scan to discover devices on local network."""
    
    def run(self, target: str = "local") -> TestResult:
        """
        Run ARP scan. Target is ignored (always scans local ARP table).
        """
        start_time = datetime.now()
        os_type = platform.system()
        
        # Build ARP command based on OS
        if os_type == "Windows":
            command = ["arp", "-a"]
        else:
            # Try ip neigh first (Linux), fallback to arp -a (macOS/Linux)
            command = ["ip", "neigh", "show"] if shutil.which("ip") else ["arp", "-a"]
        
        # Execute command
        result = self.executor.run_command(command)
        
        # Parse output
        devices = parse_arp_output(result.stdout, os_type) if result.success else []
        
        # Determine status
        if result.success:
            status = "success"
            summary = f"Found {len(devices)} device(s) in ARP table"
        else:
            status = "failure"
            summary = f"ARP scan failed: {result.stderr}"
        
        metrics: Dict[str, Any] = {
            "device_count": len(devices),
            "devices": devices,
        }
        
        test_result = TestResult(
            test_name="ARP Scan",
            target=target,
            status=status,
            timestamp=start_time,
            duration=result.duration,
            metrics=metrics,
            summary=summary,
            raw_output=result.stdout,
            error=result.stderr if not result.success else None,
        )
        
        self._log_to_csv(test_result)
        return test_result
    
    def parse_output(self, output: str) -> Dict[str, Any]:
        """Parse ARP output (handled in run())."""
        return {}
    
    def _log_to_csv(self, result: TestResult) -> None:
        """Log each device as a CSV row."""
        devices = result.metrics.get("devices", [])
        for device in devices:
            self.csv_handler.write_result(
                timestamp=result.timestamp,
                test_name=result.test_name,
                target=device.get("ip", ""),
                metric="mac_address",
                value=device.get("mac", ""),
                status=result.status,
                details=f"Interface: {device.get('interface', 'N/A')}, Vendor: {device.get('vendor', 'Unknown')}",
            )
