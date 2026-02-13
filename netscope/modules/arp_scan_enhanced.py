"""
Enhanced ARP scan: discover devices on local network with comprehensive vendor identification.
"""

import platform
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from netscope.modules.base import BaseTest, TestResult
from netscope.utils.mac_vendor import lookup_vendor, get_device_info, normalize_mac


def parse_arp_output_enhanced(output: str, os_type: str) -> List[Dict[str, Any]]:
    """
    Parse ARP table output into list of devices with enhanced vendor information.
    
    Returns:
        List of dicts with keys: ip, mac, interface, vendor, device_type
    """
    devices: List[Dict[str, Any]] = []
    seen_macs = set()  # Avoid duplicates
    
    if os_type == "Windows":
        # Windows: " 192.168.1.1           00-11-22-33-44-55     dynamic"
        pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\w+)')
        for line in output.split('\n'):
            match = pattern.search(line)
            if match:
                ip = match.group(1)
                mac = normalize_mac(match.group(2))
                
                if mac in seen_macs:
                    continue
                seen_macs.add(mac)
                
                interface = match.group(3) if len(match.groups()) > 2 else None
                device_info = get_device_info(mac, ip)
                
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": interface,
                    "vendor": device_info["vendor"],
                    "device_type": device_info["device_type"],
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
                mac = normalize_mac(macos_match.group(2))
                
                if mac in seen_macs:
                    continue
                seen_macs.add(mac)
                
                interface_match = re.search(r'on\s+(\S+)', line)
                interface = interface_match.group(1) if interface_match else None
                device_info = get_device_info(mac, ip)
                
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": interface,
                    "vendor": device_info["vendor"],
                    "device_type": device_info["device_type"],
                })
                continue
            
            # Linux ip neigh style: "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55"
            linux_match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+dev\s+(\S+)\s+lladdr\s+([0-9a-fA-F:]{17})', line)
            if linux_match:
                ip = linux_match.group(1)
                interface = linux_match.group(2)
                mac = normalize_mac(linux_match.group(3))
                
                if mac in seen_macs:
                    continue
                seen_macs.add(mac)
                
                device_info = get_device_info(mac, ip)
                
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": interface,
                    "vendor": device_info["vendor"],
                    "device_type": device_info["device_type"],
                })
                continue
            
            # Fallback: try to find IP and MAC anywhere in line
            ip_match = re.search(r'\b(\d+\.\d+\.\d+\.\d+)\b', line)
            mac_match = re.search(r'\b([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})\b', line)
            if ip_match and mac_match:
                ip = ip_match.group(1)
                mac = normalize_mac(mac_match.group(1))
                
                if mac in seen_macs:
                    continue
                seen_macs.add(mac)
                
                device_info = get_device_info(mac, ip)
                
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "interface": None,
                    "vendor": device_info["vendor"],
                    "device_type": device_info["device_type"],
                })
    
    return devices


class ARPScanTestEnhanced(BaseTest):
    """Enhanced ARP table scan with comprehensive device identification."""
    
    def run(self, target: str = "local") -> TestResult:
        """
        Run enhanced ARP scan. Target is ignored (always scans local ARP table).
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
        
        # Parse output with enhanced vendor lookup
        devices = parse_arp_output_enhanced(result.stdout, os_type) if result.success else []
        
        # Categorize devices by type
        device_types = {}
        for device in devices:
            dtype = device.get("device_type", "Unknown")
            device_types[dtype] = device_types.get(dtype, 0) + 1
        
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
            "device_types": device_types,
        }
        
        test_result = TestResult(
            test_name="ARP Scan (Enhanced)",
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
                metric="device_info",
                value=device.get("mac", ""),
                status=result.status,
                details=f"Vendor: {device.get('vendor', 'Unknown')}, Type: {device.get('device_type', 'Unknown')}, Interface: {device.get('interface', 'N/A')}",
            )
