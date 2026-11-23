"""Publishes the plugins' ``sensors()`` values to Home Assistant through MQTT discovery.

Each sensor dict: key, name, state, and optionally component ("sensor" | "binary_sensor"),
unit, icon, device_class, state_class, attributes. Credentials come from the Supervisor
(``services: mqtt:want``) or MQTT_HOST/MQTT_PORT/MQTT_USER/MQTT_PASSWORD when testing locally.
"""

import json
import logging
import os
import threading
import time
import urllib.request

import paho.mqtt.client as mqtt

log = logging.getLogger("mcp_toolbox.publisher")
PREFIX = "mcp_toolbox"
DEVICE = {"identifiers": [PREFIX], "name": "MCP Toolbox", "manufacturer": "silvinus", "model": "Home Assistant app"}


def _mqtt_settings() -> dict | None:
    if os.environ.get("MQTT_HOST"):
        return {"host": os.environ["MQTT_HOST"], "port": int(os.environ.get("MQTT_PORT", "1883")),
                "username": os.environ.get("MQTT_USER"), "password": os.environ.get("MQTT_PASSWORD")}
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    req = urllib.request.Request("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.load(response)["data"]
    return {"host": data["host"], "port": data["port"], "username": data.get("username"), "password": data.get("password")}


def _connect(settings: dict) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=PREFIX)
    if settings.get("username"):
        client.username_pw_set(settings["username"], settings.get("password"))
    client.will_set(f"{PREFIX}/status", "offline", retain=True)
    client.connect(settings["host"], settings["port"])
    client.loop_start()
    client.publish(f"{PREFIX}/status", "online", retain=True)
    return client


def _publish(client: mqtt.Client, sensor: dict, expire_after: int) -> None:
    component = sensor.get("component", "sensor")
    key = sensor["key"]
    base = f"{PREFIX}/{key}"
    config = {
        "name": sensor["name"],
        "unique_id": f"{PREFIX}_{key}",
        "default_entity_id": f"{component}.{PREFIX}_{key}",
        "state_topic": f"{base}/state",
        "json_attributes_topic": f"{base}/attributes",
        "availability_topic": f"{PREFIX}/status",
        "expire_after": expire_after,
        "device": DEVICE,
    }
    for field, ha_field in (("unit", "unit_of_measurement"), ("icon", "icon"),
                            ("device_class", "device_class"), ("state_class", "state_class")):
        if sensor.get(field):
            config[ha_field] = sensor[field]
    client.publish(f"homeassistant/{component}/{PREFIX}/{key}/config", json.dumps(config), retain=True)
    state = sensor["state"]
    client.publish(f"{base}/state", "unknown" if state is None else str(state), retain=True)
    client.publish(f"{base}/attributes", json.dumps(sensor.get("attributes", {}), ensure_ascii=False), retain=True)


def _loop(plugins: list, interval_s: float) -> None:
    client = None
    while True:
        try:
            if client is None:
                settings = _mqtt_settings()
                if settings is None:
                    log.info("No MQTT broker available: sensors are not published")
                    return
                client = _connect(settings)
            count = 0
            for plugin in plugins:
                if not hasattr(plugin, "sensors"):
                    continue
                try:
                    for sensor in plugin.sensors():
                        _publish(client, sensor, expire_after=int(interval_s * 3))
                        count += 1
                except Exception:
                    log.exception("Sensors of plugin %s failed", plugin.__name__)
            log.info("Published %d sensor(s)", count)
        except Exception:
            log.exception("Publisher round failed")
            client = None
        time.sleep(interval_s)


def start_publisher(plugins: list, interval_minutes: float) -> None:
    threading.Thread(target=_loop, args=(plugins, interval_minutes * 60), name="sensor-publisher", daemon=True).start()
