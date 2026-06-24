"""
OpsBrain — Cross-platform system info utilities

Provides CPU, memory, disk, network info on both Windows and Linux.
"""

from __future__ import annotations

import os
import platform
import socket
import struct
import ipaddress
from pathlib import Path
from typing import Any


def get_cpu_info() -> dict:
    """Return CPU model name and core count."""
    cpu_model = "Unknown"
    cpu_cores = os.cpu_count() or 0

    if os.name != "nt":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

    if cpu_model == "Unknown":
        cpu_model = platform.processor() or "Unknown"

    return {"model": cpu_model, "cores": cpu_cores}


def get_memory_info() -> dict:
    """Return memory stats in MB."""
    if os.name == "nt":
        return _memory_windows()
    return _memory_linux()


def _memory_windows() -> dict:
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(stat)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        total = stat.ullTotalPhys // (1024 * 1024)
        avail = stat.ullAvailPhys // (1024 * 1024)
        return {"total_mb": total, "used_mb": total - avail, "free_mb": avail,
                "pct": round((total - avail) / total * 100, 1) if total else 0}
    return {"total_mb": 0, "used_mb": 0, "free_mb": 0, "pct": 0}


def _memory_linux() -> dict:
    mem_total = mem_free = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    mem_total = int(line.split()[1]) // 1024
                elif "MemAvailable" in line:
                    mem_free = int(line.split()[1]) // 1024
                elif "MemFree" in line and not mem_free:
                    mem_free = int(line.split()[1]) // 1024
    except Exception:
        pass
    mem_used = mem_total - mem_free
    return {"total_mb": mem_total, "used_mb": mem_used, "free_mb": mem_free,
            "pct": round(mem_used / mem_total * 100, 1) if mem_total else 0}


def get_disk_info(path: str | None = None) -> dict:
    """Return disk total/free in GB using shutil (cross-platform)."""
    import shutil
    if path is None:
        if os.name == "nt":
            path = str(Path.home() / ".opsbrain")
        else:
            path = "/var/lib/opsbrain" if os.path.exists("/var/lib/opsbrain") else "/"
    try:
        usage = shutil.disk_usage(path)
        return {"total_gb": usage.total // (1024 ** 3), "free_gb": usage.free // (1024 ** 3)}
    except Exception:
        return {"total_gb": 0, "free_gb": 0}


def get_local_ips() -> list[str]:
    """Return all non-loopback local IP addresses."""
    ips = []
    if os.name == "nt":
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if not ip.startswith("127."):
                    ips.append(ip)
        except Exception:
            pass
    else:
        try:
            import subprocess
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3)
            ips = [ip.strip() for ip in result.stdout.split() if ip.strip()]
        except Exception:
            pass
    if not ips:
        try:
            ips = [socket.gethostbyname(socket.gethostname())]
        except Exception:
            ips = ["unknown"]
    return list(dict.fromkeys(ips))


def detect_local_subnets() -> list[str]:
    """Detect local network subnets (cross-platform)."""
    if os.name == "nt":
        return _subnets_windows()
    return _subnets_linux()


def get_gateway_ip() -> str | None:
    """Get the default gateway IP address (优先返回局域网网关)."""
    import subprocess
    gateways = []
    try:
        if os.name == "nt":
            result = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5)
            current_ip = ""
            for line in result.stdout.splitlines():
                if "IPv4 Address" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        current_ip = parts[-1].strip()
                if "默认网关" in line or "Default Gateway" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        gw = parts[-1].strip()
                        if gw and gw != "0.0.0.0":
                            gateways.append((current_ip, gw))
        else:
            result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5)
            parts = result.stdout.split()
            if "via" in parts:
                gateways.append(("", parts[parts.index("via") + 1]))
    except Exception:
        pass
    
    if not gateways:
        return None
    
    # 优先返回局域网网关（192.168.x.x, 10.x.x.x, 172.16-31.x.x）
    for ip, gw in gateways:
        if gw.startswith("192.168.") or gw.startswith("10.") or \
           any(gw.startswith(f"172.{i}.") for i in range(16, 32)):
            return gw
    
    # 如果没有局域网网关，返回第一个
    return gateways[0][1]


def _subnets_windows() -> list[str]:
    """Detect subnets, prioritizing the LAN adapter (one with a gateway)."""
    import subprocess
    # Step 1: Find the gateway's subnet to prioritize LAN
    gw = get_gateway_ip()
    lan_subnet = None
    if gw:
        try:
            lan_subnet = str(ipaddress.IPv4Network(f"{gw}/24", strict=False))
        except ValueError:
            pass

    # Step 2: Collect all subnets from adapters
    subnets = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            # Filter out known virtual/private adapter ranges that are NOT real LAN
            # VPN/WARP
            if ip.startswith("198.18."):
                continue
            # 172.16-31.x.x virtual adapters (WSL2, Hyper-V, Docker)
            # These are typically virtual; real corporate 172.x LANs will be caught via gateway check
            if ip.startswith("172.16.") or ip.startswith("172.17.") or \
               ip.startswith("172.18.") or ip.startswith("172.19.") or \
               ip.startswith("172.20.") or ip.startswith("172.21.") or \
               ip.startswith("172.22.") or ip.startswith("172.23.") or \
               ip.startswith("172.24.") or ip.startswith("172.25.") or \
               ip.startswith("172.26.") or ip.startswith("172.27.") or \
               ip.startswith("172.28.") or ip.startswith("172.29.") or \
               ip.startswith("172.30.") or ip.startswith("172.31."):
                continue
            try:
                net = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                subnets.append(str(net))
            except ValueError:
                pass
    except Exception:
        pass

    # Step 3: If gateway subnet found, put it first
    if lan_subnet and lan_subnet in subnets:
        subnets.remove(lan_subnet)
        subnets.insert(0, lan_subnet)
    elif lan_subnet:
        subnets.insert(0, lan_subnet)

    if not subnets:
        subnets = _fallback_subnets()
    return list(dict.fromkeys(subnets))


def _subnets_linux() -> list[str]:
    subnets = []
    try:
        with open("/proc/net/route", "r", encoding="utf-8", errors="ignore") as fh:
            next(fh, None)
            for line in fh:
                parts = line.split()
                if len(parts) < 8:
                    continue
                dest_hex, mask_hex = parts[1], parts[7]
                if dest_hex == "00000000" or mask_hex == "00000000":
                    continue
                dest = socket.inet_ntoa(struct.pack("<L", int(dest_hex, 16)))
                mask = socket.inet_ntoa(struct.pack("<L", int(mask_hex, 16)))
                net = ipaddress.IPv4Network(f"{dest}/{mask}", strict=False)
                if not str(net.network_address).startswith("127."):
                    subnets.append(str(net))
    except Exception:
        pass
    if not subnets:
        subnets = _fallback_subnets()
    return list(dict.fromkeys(subnets))


def _fallback_subnets() -> list[str]:
    return ["10.0.0.0/24", "172.16.0.0/24", "192.168.0.0/24", "192.168.1.0/24"]


def detect_container() -> bool:
    """Detect if running inside a container."""
    if os.name == "nt":
        return False
    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
            if any(k in text for k in ("docker", "kubepods", "containerd")):
                return True
    except Exception:
        pass
    return os.path.exists("/.dockerenv")


def get_data_dir() -> Path:
    """Return the platform-appropriate data directory."""
    env = os.environ.get("OPSBRAIN_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path.home() / ".opsbrain"
    return Path("/var/lib/opsbrain")


def get_config_dir() -> Path:
    """Return the platform-appropriate config directory."""
    if os.name == "nt":
        return Path.home() / ".opsbrain" / "config"
    return Path("/etc/opsbrain")
