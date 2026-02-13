"""
Gather network information: netmask, gateway, DNS, interface, provider/location.
Cross-platform (Linux, macOS, Windows).
"""

from __future__ import annotations

import platform
import re
import socket
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class NetworkInfo:
    """Network information for the current host."""

    interface: str = ""
    netmask: str = ""
    gateway_ip: str = ""
    gateway_mac: str = ""
    dns_servers: list[str] = field(default_factory=list)
    local_ip: str = ""
    public_ip: str = ""
    provider: str = ""
    location: str = ""


def _get_local_ip() -> str:
    """Get primary local IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2.0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip or ""
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname()) or ""
        except OSError:
            return ""


def _get_public_ip(timeout: float = 2.0) -> str:
    """Get public IPv4 address."""
    try:
        req = urllib.request.Request(
            "https://api.ipify.org",
            headers={"User-Agent": "NetScope/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode().strip() or ""
    except Exception:
        return ""


def _get_provider_and_location(public_ip: str, timeout: float = 2.0) -> tuple[str, str]:
    """Get ISP/provider and location from public IP (e.g. ip-api.com). Returns (provider, location)."""
    if not public_ip:
        return "", ""
    try:
        url = f"http://ip-api.com/json/{public_ip}?fields=isp,country,city,regionName"
        req = urllib.request.Request(url, headers={"User-Agent": "NetScope/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode()
    except Exception:
        return "", ""
    try:
        import json
        j = json.loads(data)
        isp = j.get("isp") or ""
        parts = [p for p in (j.get("city"), j.get("regionName"), j.get("country")) if p]
        location = ", ".join(parts) if parts else ""
        return isp, location
    except Exception:
        return "", ""


def _parse_arp_for_mac(ip: str, os_type: str) -> str:
    """Get MAC address for an IP from ARP table."""
    if not ip:
        return ""
    try:
        if os_type == "Windows":
            out = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        else:
            out = subprocess.run(
                ["arp", "-a"] if not __import__("shutil").which("ip") else ["ip", "neigh", "show"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        if out.returncode != 0:
            return ""
        # Look for line containing this IP and a MAC
        mac_pattern = re.compile(r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})")
        for line in (out.stdout or "").splitlines():
            if ip in line:
                m = mac_pattern.search(line)
                if m:
                    return m.group(1)
        return ""
    except Exception:
        return ""


def get_network_info(timeout: float = 2.0) -> NetworkInfo:
    """
    Gather network information for the current host.
    Uses OS-appropriate commands (ip/ifconfig/netstat/ipconfig/scutil).
    """
    info = NetworkInfo()
    os_type = platform.system()

    # Local and public IP
    info.local_ip = _get_local_ip()
    info.public_ip = _get_public_ip(timeout)

    if os_type == "Linux":
        # Gateway: ip route | grep default
        try:
            out = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0 and out.stdout:
                # default via 192.168.1.1 dev eth0 ...
                m = re.search(r"default\s+via\s+(\S+)\s+dev\s+(\S+)", out.stdout)
                if m:
                    info.gateway_ip = m.group(1)
                    info.interface = m.group(2)
            # Netmask from ip addr show <iface>
            if info.interface:
                out2 = subprocess.run(
                    ["ip", "addr", "show", info.interface],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if out2.returncode == 0:
                    # inet 192.168.1.10/24 ...
                    m = re.search(r"inet\s+\S+/(\d+)", out2.stdout)
                    if m:
                        prefix = int(m.group(1))
                        info.netmask = f"/{prefix}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        # DNS: /etc/resolv.conf
        try:
            resolv = Path("/etc/resolv.conf")
            if resolv.exists():
                for line in resolv.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) >= 2:
                            info.dns_servers.append(parts[1])
        except Exception:
            pass

    elif os_type == "Darwin":
        # macOS: netstat -nr | grep default, then ifconfig for netmask
        try:
            out = subprocess.run(
                ["netstat", "-nr"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0:
                for line in out.stdout.splitlines():
                    if "default" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            info.gateway_ip = parts[1]
                            break
            # Interface and netmask from ifconfig (first en* with inet)
            out2 = subprocess.run(
                ["ifconfig"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out2.returncode == 0:
                current_iface = None
                for line in out2.stdout.splitlines():
                    if not line.startswith("\t") and not line.startswith(" "):
                        current_iface = line.split(":")[0]
                    if "inet " in line and "127.0.0.1" not in line and current_iface:
                        m = re.search(r"inet\s+(\S+)\s+netmask\s+0x([0-9a-fA-F]+)", line)
                        if m and m.group(1) == info.local_ip:
                            info.interface = current_iface
                            # Convert hex netmask to dotted decimal
                            hex_mask = m.group(2)
                            try:
                                n = int(hex_mask, 16)
                                parts = [
                                    (n >> 24) & 0xFF,
                                    (n >> 16) & 0xFF,
                                    (n >> 8) & 0xFF,
                                    n & 0xFF,
                                ]
                                info.netmask = ".".join(str(p) for p in parts)
                            except ValueError:
                                pass
                            break
            # DNS: scutil --dns
            out3 = subprocess.run(
                ["scutil", "--dns"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out3.returncode == 0:
                for line in out3.stdout.splitlines():
                    if "nameserver" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            ns = parts[1].strip()
                            if ns and ns not in info.dns_servers:
                                info.dns_servers.append(ns)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    else:
        # Windows: ipconfig
        try:
            out = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if out.returncode != 0:
                pass
            else:
                current = out.stdout
                # Default gateway
                gw_m = re.search(r"Default Gateway[.\s]*:\s*(\S+)", current, re.I)
                if gw_m:
                    info.gateway_ip = gw_m.group(1).strip()
                # Subnet mask and interface (adapter) from the same block as our local IP
                for block in re.split(r"\r?\n\r?\n", current):
                    if info.local_ip and info.local_ip in block:
                        mask_m = re.search(r"Subnet Mask[.\s]*:\s*(\S+)", block, re.I)
                        if mask_m:
                            info.netmask = mask_m.group(1).strip()
                        iface_m = re.search(r"adapter\s+(.+?):", block, re.I)
                        if iface_m:
                            info.interface = iface_m.group(1).strip()
                        break
                # DNS
                for m in re.finditer(r"DNS Servers[.\s]*:\s*(\S+)", current, re.I):
                    info.dns_servers.append(m.group(1).strip())
                if not info.dns_servers:
                    for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\s*\(Preferred\)", current):
                        # Often DNS is listed after "DNS Servers" with (Preferred)
                        pass
                    for m in re.finditer(r"DNS Server[^s][.\s]*:\s*(\S+)", current, re.I):
                        info.dns_servers.append(m.group(1).strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Gateway MAC from ARP
    if info.gateway_ip:
        info.gateway_mac = _parse_arp_for_mac(info.gateway_ip, os_type)

    # Provider and location from public IP
    if info.public_ip:
        info.provider, info.location = _get_provider_and_location(info.public_ip, timeout)

    return info
