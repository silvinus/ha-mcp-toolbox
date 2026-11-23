"""Website monitoring: availability + TLS certificate expiry, with an alert sent to Home Assistant on change.

Settings (app option ``env``):
  SITES=Nom|https://url;Nom 2|https://url2
  ALERT_NOTIFY=notify.mobile_app_xxx   (optional; a persistent notification is always created)
  CERT_WARN_DAYS=14
The check also runs from the sensor publisher (see ``sensors``), which is what triggers alerts.
"""

import datetime as dt
import logging
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from _common import USER_AGENT, notify

log = logging.getLogger("mcp_toolbox.sites")
_last_problems: dict[str, str] = {}


def _sites() -> list[tuple[str, str]]:
    result = []
    for entry in os.environ.get("SITES", "").split(";"):
        name, sep, url = entry.partition("|")
        if sep and url.strip():
            result.append((name.strip(), url.strip()))
    return result


def _cert_days(url: str) -> tuple[int | None, str | None]:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        return None, None
    try:
        context = ssl.create_default_context()
        with socket.create_connection((parts.hostname, parts.port or 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=parts.hostname) as tls:
                not_after = tls.getpeercert()["notAfter"]
        expires = dt.datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), dt.timezone.utc)
        return (expires - dt.datetime.now(dt.timezone.utc)).days, None
    except ssl.SSLCertVerificationError as error:
        return None, f"certificat invalide ({error.verify_message})"
    except OSError as error:
        return None, f"TLS injoignable ({type(error).__name__})"


def check_site(name: str, url: str) -> dict:
    start = time.monotonic()
    status, error = None, None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as response:
            status = response.status
    except urllib.error.HTTPError as http_error:
        status = http_error.code
    except Exception as exc:  # timeout, DNS, refused...
        error = type(exc).__name__
    elapsed = round(time.monotonic() - start, 1)
    cert_days, cert_error = _cert_days(url)
    problems = []
    if error:
        problems.append(f"injoignable ({error})")
    elif status >= 500:
        problems.append(f"erreur serveur {status}")
    if cert_error:
        problems.append(cert_error)
    elif cert_days is not None and cert_days < int(os.environ.get("CERT_WARN_DAYS", "14")):
        problems.append(f"certificat expire dans {cert_days} j")
    return {"name": name, "url": url, "status": status, "seconds": elapsed, "cert_days": cert_days, "problems": problems}


def _describe(result: dict) -> str:
    state = "PROBLÈME : " + ", ".join(result["problems"]) if result["problems"] else "OK"
    details = []
    if result["status"]:
        details.append(f"HTTP {result['status']} en {result['seconds']} s")
    if result["cert_days"] is not None:
        details.append(f"certificat valide encore {result['cert_days']} j")
    return f"- {result['name']} : {state}" + (f" ({', '.join(details)})" if details else "")


def _alert_on_change(result: dict) -> None:
    name, current = result["name"], ", ".join(result["problems"])
    previous = _last_problems.get(name, "")
    try:
        if current and current != previous:
            notify(f"⚠️ Site {name}", f"{name} ({result['url']}) : {current}.")
        elif previous and not current:
            notify(f"✅ Site {name}", f"{name} fonctionne à nouveau.")
    except Exception:
        log.exception("Could not send site alert")
    _last_problems[name] = current


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def sensors() -> list[dict]:
    out = []
    for name, url in _sites():
        result = check_site(name, url)
        _alert_on_change(result)
        out.append({
            "key": f"site_{_slug(name)}", "component": "binary_sensor", "name": f"Site {name}",
            "state": "ON" if result["problems"] else "OFF", "device_class": "problem",
            "attributes": {"url": url, "http_status": result["status"], "response_s": result["seconds"],
                           "cert_days": result["cert_days"], "problems": ", ".join(result["problems"])},
        })
        if result["cert_days"] is not None:
            out.append({"key": f"site_{_slug(name)}_cert", "name": f"Certificat {name}", "state": result["cert_days"],
                        "unit": "d", "device_class": "duration", "icon": "mdi:certificate"})
    return out


def register(mcp):
    @mcp.tool()
    def etat_sites() -> str:
        """Vérifie que les sites web surveillés (planning Ecbatan, accès externe Home Assistant...) répondent et quand expirent leurs certificats."""
        sites = _sites()
        if not sites:
            return "Aucun site configuré (réglage SITES)."
        return "État des sites :\n" + "\n".join(_describe(check_site(n, u)) for n, u in sites)
