"""Helpers shared by the built-in plugins (files starting with "_" are not loaded as plugins)."""

import json
import os
import urllib.request

USER_AGENT = "mcp-toolbox (Home Assistant app)"


def http_json(url: str, timeout: float = 15, headers: dict | None = None, data: dict | None = None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        method="POST" if body is not None else "GET",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def ha_api(path: str, data: dict | None = None):
    """Home Assistant REST API: through the Supervisor inside the app, or HA_URL/HA_TOKEN when testing locally."""
    if os.environ.get("SUPERVISOR_TOKEN"):
        base, token = "http://supervisor/core/api", os.environ["SUPERVISOR_TOKEN"]
    else:
        base, token = os.environ.get("HA_URL", "").rstrip("/") + "/api", os.environ.get("HA_TOKEN", "")
    return http_json(base + path, headers={"Authorization": f"Bearer {token}"}, data=data)


def home_location() -> tuple[float, float]:
    """Home coordinates: HOME_LAT/HOME_LON if set, otherwise the Home Assistant home zone."""
    if os.environ.get("HOME_LAT") and os.environ.get("HOME_LON"):
        return float(os.environ["HOME_LAT"]), float(os.environ["HOME_LON"])
    config = ha_api("/config")
    return float(config["latitude"]), float(config["longitude"])


def notify(title: str, message: str) -> None:
    """Persistent notification in HA, plus ALERT_NOTIFY (e.g. notify.mobile_app_x) when set."""
    ha_api("/services/persistent_notification/create", {"title": title, "message": message})
    target = os.environ.get("ALERT_NOTIFY", "")
    if target.startswith("notify."):
        ha_api(f"/services/notify/{target.removeprefix('notify.')}", {"title": title, "message": message})
