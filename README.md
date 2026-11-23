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

## Clients

- Claude Code : `claude mcp add --transport http toolbox http://192.168.1.39:8765/mcp --header "Authorization: Bearer <token>"`
- HA : intégration « Model Context Protocol », URL `http://<hostname-app>:8765/sse`. Cocher ensuite l'API dans l'agent de conversation.

## Test local

```
OPTIONS_PATH=test_options.json SHARE_TOOLS=share-example PORT=18765 python mcp_toolbox/server.py
python dev/test_client.py http://127.0.0.1:18765 <token>
```
