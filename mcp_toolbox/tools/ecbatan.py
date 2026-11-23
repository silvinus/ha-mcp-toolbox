"""Ecbatan holiday-house planning (read-only), from the app's public /api/planning endpoint.

Setting: ECBATAN_URL (app option ``env``), e.g. https://planning.example.fr
"""

import datetime as dt
import json
import os
import urllib.request

STATUS_FR = {"Pending": "demande", "Accepted": "acceptée", "Confirmed": "confirmée"}


def _fetch(year: int, month: int) -> dict:
    base = os.environ.get("ECBATAN_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("ECBATAN_URL n'est pas configurée dans l'app MCP Toolbox")
    url = f"{base}/api/planning?year={year}&month={month}"
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def _people(reservation: dict) -> str:
    adults = sum(line["adultCount"] for line in reservation.get("personLines", []))
    kids = sum(line["childrenUnder3Count"] for line in reservation.get("personLines", []))
    text = f"{adults} adulte{'s' if adults > 1 else ''}"
    if kids:
        text += f" + {kids} enfant{'s' if kids > 1 else ''} de moins de 3 ans"
    return text


def format_planning(planning: dict) -> str:
    lines = []
    for studio in planning["studios"]:
        for r in sorted(studio["reservations"], key=lambda r: r["startDate"]):
            start = dt.date.fromisoformat(r["startDate"])
            end = dt.date.fromisoformat(r["endDate"])
            status = STATUS_FR.get(r["status"], r["status"])
            if r.get("isHypothetical"):
                status += ", hypothétique"
            lines.append(
                f"- {studio['studio']['name']} : {r['tenantName']} (propriétaire {r['ownerName']}), "
                f"arrivée {start:%d/%m}, départ {end:%d/%m}, {_people(r)}, {status}"
            )
    header = f"Planning Ecbatan {planning['month']:02d}/{planning['year']}"
    if not lines:
        return f"{header} : aucune réservation."
    return header + " (le jour de départ est libre) :\n" + "\n".join(lines)


def register(mcp):
    @mcp.tool()
    def planning_ecbatan(mois: str = "") -> str:
        """Réservations de la maison de vacances Ecbatan pour un mois : qui occupe quel logement, dates, nombre de personnes, statut. mois au format AAAA-MM, mois en cours si vide."""
        if mois:
            year, month = (int(part) for part in mois.split("-")[:2])
        else:
            today = dt.date.today()
            year, month = today.year, today.month
        return format_planning(_fetch(year, month))
