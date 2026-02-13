"""
Smart target resolution: convert shortcuts like "localhost", "gateway", "dns" to actual targets.
"""

import socket
import platform
import subprocess
from typing import Optional


def resolve_target_shortcut(target: str) -> Optional[str]:
    """
    Resolve smart shortcuts to actual targets.
    
    Returns:
        Resolved target (IP or hostname), or None if shortcut not recognized.
    """
    target_lower = target.lower().strip()

    if target_lower == "localhost" or target_lower == "local":
        return "127.0.0.1"

    if target_lower == "gateway" or target_lower == "router":
        return _get_default_gateway()

    if target_lower == "dns" or target_lower == "dns-server":
        return _get_dns_server()

    # Not a shortcut
    return None


def _get_default_gateway() -> str:
    """Get default gateway IP address."""
    os_type = platform.system()

    try:
        if os_type == "Windows":
            # Use route print to find default gateway
            result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "0.0.0.0" in line and "On-link" not in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "0.0.0.0" and i + 1 < len(parts):
                            gateway = parts[i + 1]
                            if _is_valid_ip(gateway):
                                return gateway
        else:
            # Linux/macOS: use ip route or netstat
            # Try ip route first (Linux)
            try:
                result = subprocess.run(
                    ["ip", "route", "show", "default"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "default via" in line:
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if part == "via" and i + 1 < len(parts):
                                    gateway = parts[i + 1]
                                    if _is_valid_ip(gateway):
                                        return gateway
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Fallback: netstat (macOS/Linux)
            try:
                result = subprocess.run(
                    ["netstat", "-rn"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if line.startswith("default") or line.startswith("0.0.0.0"):
                            parts = line.split()
                            if len(parts) >= 2:
                                gateway = parts[1]
                                if _is_valid_ip(gateway):
                                    return gateway
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    except Exception:
        pass

    # Fallback: common defaults
    return "192.168.1.1"


def _get_dns_server() -> str:
    """Get primary DNS server IP."""
    os_type = platform.system()

    try:
        if os_type == "Windows":
            # Use ipconfig /all
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "DNS Servers" in line or "DNS servers" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        dns = parts[1].strip()
                        if _is_valid_ip(dns):
                            return dns
        else:
            # Linux/macOS: check /etc/resolv.conf
            try:
                with open("/etc/resolv.conf", "r") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            dns = line.split()[1].strip()
                            if _is_valid_ip(dns):
                                return dns
            except (FileNotFoundError, PermissionError):
                pass
    except Exception:
        pass

    # Fallback: common public DNS
    return "8.8.8.8"


def _is_valid_ip(ip: str) -> bool:
    """Check if string is a valid IPv4 address."""
    try:
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True
    except ValueError:
        return False
