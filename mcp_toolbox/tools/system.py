"""Built-in tool: health of the machine hosting the server."""

import os
import pathlib
import shutil


def _read(path: str) -> str | None:
    try:
        return pathlib.Path(path).read_text().strip()
    except OSError:
        return None


def register(mcp):
    @mcp.tool()
    def pi_status() -> dict:
        """État du Raspberry Pi : température CPU, charge, mémoire, disque, uptime."""
        uptime_s = float((_read("/proc/uptime") or "0").split()[0])
        meminfo = {}
        for line in (_read("/proc/meminfo") or "").splitlines():
            key, _, value = line.partition(":")
            meminfo[key] = int(value.split()[0]) // 1024 if value.split() else 0
        temp = _read("/sys/class/thermal/thermal_zone0/temp")
        disk = shutil.disk_usage("/")
        return {
            "cpu_temp_c": round(int(temp) / 1000, 1) if temp else None,
            "load_1_5_15": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
            "memory_mb": {"total": meminfo.get("MemTotal"), "available": meminfo.get("MemAvailable")},
            "disk_gb": {"total": round(disk.total / 1e9, 1), "free": round(disk.free / 1e9, 1)},
            "uptime_hours": round(uptime_s / 3600, 1),
        }
