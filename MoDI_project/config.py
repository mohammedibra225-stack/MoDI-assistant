"""Gestion de la configuration locale de ModI (clé API, modèle, voix...).

Le fichier modi_config.json est créé automatiquement à côté de ce script
au premier lancement. Il est volontairement exclu du dépôt Git (voir
.gitignore) car il contient ta clé API personnelle.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "modi_config.json"

DEFAULT_CONFIG = {
    "hf_token": "",
    "hf_model": "openai/gpt-oss-120b",  # modèle recommandé par Hugging Face pour l'utilisation d'outils
    "system_prompt": (
        "Tu es ModI, un assistant IA futuriste inspiré d'Iron Man. "
        "Tu réponds toujours en français, de façon concise (2 à 4 phrases "
        "sauf si on te demande plus de détails), avec un ton calme, "
        "professionnel et un peu pince-sans-rire. "
        "Tu as accès à des outils pour chercher, ouvrir, lire, écrire et "
        "supprimer des fichiers sur l'ordinateur de l'utilisateur : utilise-les "
        "dès que la demande le justifie, sans jamais inventer un résultat, et "
        "résume toujours clairement ce que tu as fait à la fin."
    ),
    "voice_rate": 160,
    "voice_volume": 90,
}


def load_config():
    """Charge la configuration depuis modi_config.json (ou les valeurs par défaut)."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    """Sauvegarde la configuration. Retourne True si l'écriture a réussi."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
