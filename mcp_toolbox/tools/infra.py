"""Infra & dev status, mostly for Claude: local AI services on the PC and GitHub repositories.

Settings: OLLAMA_URL=http://192.168.1.4:11434, WHISPER_ADDR=192.168.1.4:10300,
          GITHUB_REPOS=owner/repo,owner/repo2, GITHUB_TOKEN (optional: higher rate limit, private repos)
"""

import datetime as dt
import os
import socket

from _common import http_json


def _age(iso: str) -> str:
    delta = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return f"{delta.days} j" if delta.days else f"{delta.seconds // 3600} h"


def ollama_status() -> dict | None:
    base = os.environ.get("OLLAMA_URL", "").rstrip("/")
    if not base:
        return None
    try:
        version = http_json(f"{base}/api/version", timeout=5).get("version")
        loaded = http_json(f"{base}/api/ps", timeout=5).get("models", [])
        return {"up": True, "version": version, "models": [m["name"] for m in loaded],
                "vram_gb": round(sum(m.get("size_vram", 0) for m in loaded) / 1e9, 1)}
    except Exception as error:
        return {"up": False, "error": type(error).__name__}


def whisper_status() -> dict | None:
    addr = os.environ.get("WHISPER_ADDR", "")
    if not addr:
        return None
    host, _, port = addr.rpartition(":")
    try:
        socket.create_connection((host, int(port)), timeout=5).close()
        return {"up": True, "addr": addr}
    except OSError as error:
        return {"up": False, "addr": addr, "error": type(error).__name__}


def github_status() -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    result = []
    for repo in [r.strip() for r in os.environ.get("GITHUB_REPOS", "").split(",") if r.strip()]:
        try:
            pulls = http_json(f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=30", headers=headers)
            runs = http_json(f"https://api.github.com/repos/{repo}/actions/runs?per_page=30", headers=headers)["workflow_runs"]
        except Exception as error:
            result.append({"repo": repo, "error": type(error).__name__})
            continue
        latest = {}
        for run in runs:  # newest first: keep the latest run of each workflow
            latest.setdefault(run["name"], run)
        result.append({
            "repo": repo,
            "pulls": [{"number": p["number"], "title": p["title"], "author": p["user"]["login"], "age": _age(p["created_at"])} for p in pulls],
            "runs": [{"workflow": n, "branch": r["head_branch"], "result": r["conclusion"] or r["status"], "age": _age(r["created_at"])}
                     for n, r in latest.items()],
        })
    return result


def sensors() -> list[dict]:
    out = []
    ollama = ollama_status()
    if ollama is not None:
        out.append({"key": "ollama", "component": "binary_sensor", "name": "Ollama", "state": "ON" if ollama["up"] else "OFF",
                    "device_class": "running", "attributes": {k: v for k, v in ollama.items() if k != "up"}})
    whisper = whisper_status()
    if whisper is not None:
        out.append({"key": "whisper", "component": "binary_sensor", "name": "Whisper", "state": "ON" if whisper["up"] else "OFF",
                    "device_class": "running", "attributes": {k: v for k, v in whisper.items() if k != "up"}})
    for repo in github_status():
        slug = repo["repo"].split("/")[-1].lower().replace("-", "_")
        if "error" in repo:
            continue
        failed = [r["workflow"] for r in repo["runs"] if r["result"] == "failure"]
        out.append({"key": f"github_{slug}_pr", "name": f"{repo['repo'].split('/')[-1]} PR ouvertes", "state": len(repo["pulls"]),
                    "icon": "mdi:source-pull", "attributes": {"pulls": [f"#{p['number']} {p['title']}" for p in repo["pulls"]]}})
        out.append({"key": f"github_{slug}_ci", "component": "binary_sensor", "name": f"{repo['repo'].split('/')[-1]} CI en échec",
                    "state": "ON" if failed else "OFF", "device_class": "problem", "attributes": {"workflows_en_echec": failed}})
    return out


def register(mcp):
    @mcp.tool()
    def etat_ia_locale() -> str:
        """État des services d'IA locale sur le PC : Ollama (modèles chargés) et Whisper (reconnaissance vocale)."""
        lines = []
        ollama = ollama_status()
        if ollama:
            if ollama["up"]:
                models = ", ".join(ollama["models"]) or "aucun modèle chargé"
                lines.append(f"- Ollama {ollama['version']} : en marche ({models}, {ollama['vram_gb']} Go en VRAM)")
            else:
                lines.append(f"- Ollama : injoignable ({ollama['error']})")
        whisper = whisper_status()
        if whisper:
            lines.append(f"- Whisper : {'en écoute' if whisper['up'] else 'injoignable (' + whisper['error'] + ')'} sur {whisper['addr']}")
        return "IA locale :\n" + "\n".join(lines) if lines else "Aucun service configuré (OLLAMA_URL, WHISPER_ADDR)."

    @mcp.tool()
    def etat_github() -> str:
        """PR ouvertes et derniers résultats CI/CD des dépôts GitHub suivis."""
        repos = github_status()
        if not repos:
            return "Aucun dépôt configuré (GITHUB_REPOS)."
        out = []
        for repo in repos:
            if "error" in repo:
                out.append(f"{repo['repo']} : lecture impossible ({repo['error']})")
                continue
            out.append(f"{repo['repo']} :")
            out += [f"  - PR #{p['number']} « {p['title']} » par {p['author']}, ouverte depuis {p['age']}" for p in repo["pulls"]] or ["  - aucune PR ouverte"]
            out += [f"  - {r['workflow']} ({r['branch']}) : {r['result']}, il y a {r['age']}" for r in repo["runs"]]
        return "\n".join(out)
