# MCP Toolbox — app Home Assistant

Serveur MCP générique hébergé sur le Raspberry Pi (HAOS). Il sert les mêmes tools à Claude et aux LLM de Home Assistant (agent Ollama).

- Endpoints : `http://<pi>:8765/mcp` (Streamable HTTP) et `http://<pi>:8765/sse` (SSE)
- Auth : les réseaux de `trusted_networks` (par défaut le réseau interne de HA, `172.30.32.0/23`) passent sans token. Tous les autres envoient `Authorization: Bearer <token>`.

## Ajouter un tool

Un plugin est un fichier `.py` qui expose `register(mcp)` :

```python
def register(mcp):
    @mcp.tool()
    def mon_outil(param: str) -> str:
        """Description courte : c'est ce que lit le LLM."""
        return ...
```

Deux emplacements :
- `mcp_toolbox/tools/` (versionné) : commit, push, augmenter `version` dans `config.yaml`, puis mettre à jour l'app dans HA ;
- `/share/mcp-tools/` sur le Pi (test rapide) : redémarrer l'app suffit.

Un plugin cassé est ignoré : l'erreur est dans le journal de l'app.

Réglages des plugins : l'option `env` de l'app est une liste de `CLE=VALEUR`, transformées en variables d'environnement avant le chargement des plugins.

## Tools fournis

| Tool | Rôle | Réglages (`env`) | Assistant vocal |
|------|------|------------------|-----------------|
| `pi_status` | Température CPU, charge, mémoire, disque, uptime | — | oui |
| `planning_ecbatan(mois)` | Réservations Ecbatan du mois (`GET /api/planning`) | `ECBATAN_URL` | oui |
| `etat_sites` | Disponibilité + expiration des certificats ; alerte HA (notification) à chaque changement | `SITES=Nom\|url;…`, `ALERT_NOTIFY`, `CERT_WARN_DAYS` | oui |
| `prix_carburant(carburant, rayon_km)` | Stations les moins chères autour de la maison (data.economie.gouv.fr) | `FUEL_DEFAULT`, `FUEL_RADIUS_KM` (capteur) | oui |
| `couleur_tempo` | Couleur EDF Tempo aujourd'hui / demain, jours restants | — | oui |
| `qualite_air` | Indice européen, particules, ozone, pollens (Open-Meteo) | — | oui |
| `etat_ia_locale` | Ollama (modèles chargés) et Whisper sur le PC | `OLLAMA_URL`, `WHISPER_ADDR` | non |
| `etat_github` | PR ouvertes et derniers workflows | `GITHUB_REPOS`, `GITHUB_TOKEN` (optionnel) | non |

La position de la maison vient de la zone *home* de Home Assistant (ou de `HOME_LAT` / `HOME_LON`).

## Deux publics

- `/mcp` et `/sse` : tous les tools (Claude).
- `/ha/sse` : les mêmes, sauf ceux listés dans l'option `ha_exclude`. C'est l'URL à donner à l'intégration MCP de HA. Le petit modèle local ralentit à chaque tool ajouté.

## Capteurs Home Assistant

Un plugin peut aussi exposer `sensors()`. Les valeurs sont publiées via MQTT discovery (Mosquitto) toutes les `sensor_interval_minutes`, sur l'appareil « MCP Toolbox » : Tempo, qualité de l'air, pollens, carburant, sites, certificats, Ollama, Whisper, GitHub. La surveillance des sites tourne dans cette même boucle et envoie les alertes.

## Clients

- Claude Code : `claude mcp add --transport http toolbox http://192.168.1.39:8765/mcp --header "Authorization: Bearer <token>"`
- HA : intégration « Model Context Protocol », URL `http://<hostname-app>:8765/sse`. Cocher ensuite l'API dans l'agent de conversation.

## Test local

```
OPTIONS_PATH=test_options.json SHARE_TOOLS=share-example PORT=18765 python mcp_toolbox/server.py
python dev/test_client.py http://127.0.0.1:18765 <token>
```
