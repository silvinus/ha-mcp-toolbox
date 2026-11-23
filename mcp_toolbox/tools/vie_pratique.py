"""Everyday tools from free public APIs: fuel prices (data.economie.gouv.fr), EDF Tempo colour,
air quality and pollen (Open-Meteo). Location = Home Assistant home zone (or HOME_LAT / HOME_LON).

Settings: FUEL_DEFAULT=gazole (fuel published as a sensor), FUEL_RADIUS_KM=10
"""

import datetime as dt
import os
import urllib.parse

from _common import home_location, http_json

FUELS = {"gazole": "gazole", "diesel": "gazole", "e10": "e10", "sp95": "sp95", "sp98": "sp98", "e85": "e85", "gpl": "gplc", "gplc": "gplc"}
FUEL_API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records"
TEMPO_API = "https://www.api-couleur-tempo.fr/api"
AIR_API = "https://air-quality-api.open-meteo.com/v1/air-quality"

AQI_LABELS = [(20, "bonne"), (40, "correcte"), (60, "moyenne"), (80, "médiocre"), (100, "mauvaise")]
POLLENS = {"alder_pollen": "aulne", "birch_pollen": "bouleau", "grass_pollen": "graminées",
           "mugwort_pollen": "armoise", "ragweed_pollen": "ambroisie"}


def _aqi_label(aqi) -> str:
    if aqi is None:
        return "inconnue"
    return next((text for limit, text in AQI_LABELS if aqi < limit), "très mauvaise")


def _pollen_level(value: float) -> str:
    if value < 1:
        return "nul"
    if value < 20:
        return "faible"
    if value < 80:
        return "moyen"
    return "élevé"


def fuel_stations(carburant: str, rayon_km: int, limit: int = 5) -> tuple[str, list[dict]]:
    fuel = FUELS.get(carburant.lower().replace(" ", ""))
    if not fuel:
        raise ValueError(carburant)
    lat, lon = home_location()
    where = f"within_distance(geom, geom'POINT({lon} {lat})', {int(rayon_km)}km) and {fuel}_prix is not null"
    query = urllib.parse.urlencode({"where": where, "order_by": f"{fuel}_prix", "limit": limit})
    records = http_json(f"{FUEL_API}?{query}", timeout=20)["results"]
    stations = [{
        "price": r[f"{fuel}_prix"],
        "address": f"{r['adresse'].title()}, {r['ville'].title()}",
        "updated": dt.datetime.fromisoformat(r[f"{fuel}_maj"]).astimezone().strftime("%d/%m %Hh"),
    } for r in records]
    return fuel, stations


def tempo() -> dict:
    today = http_json(f"{TEMPO_API}/jourTempo/today")
    tomorrow = http_json(f"{TEMPO_API}/jourTempo/tomorrow")
    stats = http_json(f"{TEMPO_API}/stats")
    return {"today": today.get("libCouleur") or "inconnue",
            "tomorrow": tomorrow.get("libCouleur") or "inconnue",
            "red_left": stats["joursRougesRestants"], "white_left": stats["joursBlancsRestants"],
            "blue_left": stats["joursBleusRestants"]}


def air() -> dict:
    lat, lon = home_location()
    fields = ["european_aqi", "pm10", "pm2_5", "ozone", "nitrogen_dioxide", *POLLENS]
    query = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "current": ",".join(fields), "timezone": "Europe/Paris"})
    return http_json(f"{AIR_API}?{query}")["current"]


def sensors() -> list[dict]:
    out = []
    t = tempo()
    out.append({"key": "tempo_aujourdhui", "name": "Tempo aujourd'hui", "state": t["today"], "icon": "mdi:flash"})
    out.append({"key": "tempo_demain", "name": "Tempo demain", "state": t["tomorrow"], "icon": "mdi:flash-outline"})
    out.append({"key": "tempo_rouges_restants", "name": "Tempo jours rouges restants", "state": t["red_left"], "unit": "j", "icon": "mdi:calendar-alert"})
    a = air()
    out.append({"key": "qualite_air", "name": "Qualité de l'air (indice européen)", "state": a.get("european_aqi"),
                "icon": "mdi:air-filter", "state_class": "measurement",
                "attributes": {"niveau": _aqi_label(a.get("european_aqi")), "pm2_5": a.get("pm2_5"), "pm10": a.get("pm10"),
                               "ozone": a.get("ozone"), "no2": a.get("nitrogen_dioxide")}})
    for key, name in POLLENS.items():
        value = a.get(key) or 0
        out.append({"key": f"pollen_{key.removesuffix('_pollen')}", "name": f"Pollen {name}", "state": value,
                    "unit": "grains/m³", "icon": "mdi:flower-pollen", "state_class": "measurement",
                    "attributes": {"niveau": _pollen_level(value)}})
    carburant = os.environ.get("FUEL_DEFAULT", "gazole")
    _, stations = fuel_stations(carburant, int(os.environ.get("FUEL_RADIUS_KM", "10")), limit=3)
    if stations:
        best = stations[0]
        out.append({"key": f"carburant_{carburant}", "name": f"{carburant.capitalize()} le moins cher", "state": best["price"],
                    "unit": "€/L", "icon": "mdi:gas-station", "state_class": "measurement",
                    "attributes": {"station": best["address"], "mis_a_jour": best["updated"],
                                   "autres": [f"{s['price']:.3f} € {s['address']}" for s in stations[1:]]}})
    return out


def register(mcp):
    @mcp.tool()
    def prix_carburant(carburant: str = "gazole", rayon_km: int = 10) -> str:
        """Stations les moins chères autour de la maison pour un carburant (gazole, e10, sp95, sp98, e85, gpl)."""
        try:
            _, stations = fuel_stations(carburant, rayon_km)
        except ValueError:
            return f"Carburant inconnu : {carburant}. Choix : gazole, e10, sp95, sp98, e85, gpl."
        if not stations:
            return f"Aucune station avec du {carburant} à moins de {rayon_km} km."
        lines = [f"- {s['price']:.3f} €/L : {s['address']} (mis à jour {s['updated']})" for s in stations]
        return f"{carburant.capitalize()} le moins cher à moins de {rayon_km} km :\n" + "\n".join(lines)

    @mcp.tool()
    def couleur_tempo() -> str:
        """Couleur EDF Tempo d'aujourd'hui et de demain (bleu, blanc, rouge) et jours restants dans la saison."""
        t = tempo()
        tomorrow = t["tomorrow"] if t["tomorrow"] != "inconnue" else "pas encore annoncée (vers 11 h)"
        return (f"Tempo aujourd'hui : {t['today']}. Demain : {tomorrow}. Restent cette saison : "
                f"{t['red_left']} jours rouges, {t['white_left']} blancs, {t['blue_left']} bleus.")

    @mcp.tool()
    def qualite_air() -> str:
        """Qualité de l'air et niveaux de pollens actuels autour de la maison."""
        a = air()
        active = [f"{name} {_pollen_level(a.get(key) or 0)}" for key, name in POLLENS.items() if (a.get(key) or 0) >= 1]
        return (f"Qualité de l'air {_aqi_label(a.get('european_aqi'))} (indice européen {a.get('european_aqi')}). "
                f"PM2,5 {a.get('pm2_5')} µg/m³, PM10 {a.get('pm10')} µg/m³, ozone {a.get('ozone')} µg/m³. "
                f"Pollens : {', '.join(active) if active else 'aucun pollen notable'}.")
