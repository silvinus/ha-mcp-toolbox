"""Exemple de plugin à déposer dans /share/mcp-tools/ sur le Pi."""


def register(mcp):
    @mcp.tool()
    def dire_bonjour(prenom: str) -> str:
        """Renvoie un bonjour personnalisé (outil de test)."""
        return f"Bonjour {prenom}, depuis le Raspberry Pi !"
