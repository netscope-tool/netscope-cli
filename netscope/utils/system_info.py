"""
Gather system information: OS, CPU, memory, disk, uptime.
Cross-platform (Linux, macOS, Windows).
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemInfo:
    """System information for the current host."""
    
    hostname: str = ""
    os_name: str = ""
    os_version: str = ""
    architecture: str = ""
    cpu_model: str = ""
    cpu_cores: int = 0
    cpu_usage: float = 0.0  # Percentage
    memory_total: int = 0  # MB
    memory_used: int = 0  # MB
    memory_percent: float = 0.0
    disk_total: int = 0  # GB
    disk_used: int = 0  # GB
    disk_percent: float = 0.0
    uptime: str = ""


def _get_cpu_info() -> tuple[str, int]:
    """Get CPU model and core count."""
    try:
        import psutil
        cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count() or 0
    except ImportError:
        cpu_count = 0
    
    cpu_model = ""
    os_type = platform.system()
    
    try:
        if os_type == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        elif os_type == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                cpu_model = result.stdout.strip()
        elif os_type == "Windows":
            result = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    cpu_model = lines[1].strip()
    except Exception:
        pass
    
    return cpu_model, cpu_count


def _get_memory_info() -> tuple[int, int, float]:
    """Get memory total, used, and percentage."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        used_mb = mem.used // (1024 * 1024)
        percent = mem.percent
        return total_mb, used_mb, percent
    except ImportError:
        pass
    
    # Fallback without psutil
    os_type = platform.system()
    
    try:
        if os_type == "Linux":
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
                mem_total = 0
                mem_available = 0
                for line in lines:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1]) // 1024  # KB to MB
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1]) // 1024
                if mem_total > 0:
                    mem_used = mem_total - mem_available
                    percent = (mem_used / mem_total) * 100
                    return mem_total, mem_used, percent
        elif os_type == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                total_bytes = int(result.stdout.strip())
                total_mb = total_bytes // (1024 * 1024)
                # Can't easily get used memory without psutil on macOS
                return total_mb, 0, 0.0
    except Exception:
        pass
    
    return 0, 0, 0.0


def _get_disk_info() -> tuple[int, int, float]:
    """Get disk total, used, and percentage for root partition."""
    try:
        import psutil
        disk = psutil.disk_usage("/")
        total_gb = disk.total // (1024 * 1024 * 1024)
        used_gb = disk.used // (1024 * 1024 * 1024)
        percent = disk.percent
        return total_gb, used_gb, percent
    except ImportError:
        pass
    
    # Fallback without psutil
    os_type = platform.system()
    
    try:
        if os_type in ["Linux", "Darwin"]:
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        # Size, Used, Avail, Use%, Mounted
                        total_str = parts[1].replace("G", "").replace("T", "000")
                        used_str = parts[2].replace("G", "").replace("T", "000")
                        percent_str = parts[4].replace("%", "")
                        try:
                            total_gb = int(float(total_str))
                            used_gb = int(float(used_str))
                            percent = float(percent_str)
                            return total_gb, used_gb, percent
                        except ValueError:
                            pass
    except Exception:
        pass
    
    return 0, 0, 0.0


def _get_uptime() -> str:
    """Get system uptime."""
    try:
        import psutil
        boot_time = psutil.boot_time()
        import time
        uptime_seconds = time.time() - boot_time
        
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    except ImportError:
        pass
    
    # Fallback without psutil
    os_type = platform.system()
    
    try:
        if os_type == "Linux":
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.read().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                
                if days > 0:
                    return f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    return f"{hours}h {minutes}m"
                else:
                    return f"{minutes}m"
        elif os_type == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "kern.boottime"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse: { sec = 1234567890, usec = 0 }
                import re
                import time
                m = re.search(r"sec = (\d+)", result.stdout)
                if m:
                    boot_time = int(m.group(1))
                    uptime_seconds = time.time() - boot_time
                    days = int(uptime_seconds // 86400)
                    hours = int((uptime_seconds % 86400) // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    
                    if days > 0:
                        return f"{days}d {hours}h {minutes}m"
                    elif hours > 0:
                        return f"{hours}h {minutes}m"
                    else:
                        return f"{minutes}m"
    except Exception:
        pass
    
    return "Unknown"


def _get_cpu_usage() -> float:
    """Get current CPU usage percentage."""
    try:
        import psutil
        return psutil.cpu_percent(interval=1)
    except ImportError:
        return 0.0


def get_system_info() -> SystemInfo:
    """
    Gather system information for the current host.
    """
    info = SystemInfo()
    
    # Basic platform info
    info.hostname = platform.node()
    info.os_name = platform.system()
    info.os_version = platform.release()
    info.architecture = platform.machine()
    
    # CPU
    info.cpu_model, info.cpu_cores = _get_cpu_info()
    info.cpu_usage = _get_cpu_usage()
    
    # Memory
    info.memory_total, info.memory_used, info.memory_percent = _get_memory_info()
    
    # Disk
    info.disk_total, info.disk_used, info.disk_percent = _get_disk_info()
    
    # Uptime
    info.uptime = _get_uptime()
    
    return info
