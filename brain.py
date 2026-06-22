"""Cerveau IA de ModI : appel à l'API Hugging Face (Inference Providers),
avec prise en charge de l'utilisation d'outils (function calling).
"""

import json
import requests

HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
MAX_HISTORY_MESSAGES = 12  # ~6 échanges de contexte envoyés au modèle

# Description des outils fichiers, au format function-calling compatible OpenAI.
# L'exécution réelle est faite par file_tools.FileTools ; ce module ne fait
# qu'envoyer cette description au modèle pour qu'il sache ce qu'il peut faire.
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "chercher_fichier",
            "description": "Recherche un fichier par son nom (ou une partie du nom) sur l'ordinateur de l'utilisateur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Nom ou partie du nom du fichier à chercher."},
                    "dossier": {
                        "type": "string",
                        "description": "Dossier où chercher (ex: Bureau, Documents, Téléchargements). "
                                       "Optionnel : par défaut, tout le dossier personnel de l'utilisateur.",
                    },
                },
                "required": ["nom"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ouvrir_fichier",
            "description": "Ouvre un fichier avec l'application par défaut du système.",
            "parameters": {
                "type": "object",
                "properties": {"chemin": {"type": "string", "description": "Chemin complet du fichier à ouvrir."}},
                "required": ["chemin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lire_fichier",
            "description": "Lit le contenu d'un fichier texte pour le résumer, l'analyser ou préparer une modification.",
            "parameters": {
                "type": "object",
                "properties": {"chemin": {"type": "string", "description": "Chemin complet du fichier à lire."}},
                "required": ["chemin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ecrire_fichier",
            "description": "Crée un nouveau fichier texte, remplace son contenu, ou ajoute du texte à la fin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin complet du fichier à écrire."},
                    "contenu": {"type": "string", "description": "Texte à écrire dans le fichier."},
                    "mode": {
                        "type": "string",
                        "enum": ["remplacer", "ajouter"],
                        "description": "'remplacer' écrase tout le contenu, 'ajouter' complète à la fin.",
                    },
                },
                "required": ["chemin", "contenu"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_fichier",
            "description": (
                "Supprime un fichier (déplacé dans une corbeille locale récupérable). "
                "Une confirmation manuelle de l'utilisateur est toujours requise avant l'action."
            ),
            "parameters": {
                "type": "object",
                "properties": {"chemin": {"type": "string", "description": "Chemin complet du fichier à supprimer."}},
                "required": ["chemin"],
            },
        },
    },
]


def ask_modi_brain(messages, token, model, tool_executor=None, tools=None, timeout=30, max_tool_rounds=4):
    """
    Envoie une conversation au modèle choisi via le routeur Hugging Face
    (API compatible OpenAI). Si le modèle décide d'utiliser un outil, celui-ci
    est exécuté via tool_executor(nom, arguments) puis le résultat est renvoyé
    au modèle pour obtenir une réponse finale.

    Retourne (succès: bool, texte: str).
    """
    if not token:
        return False, "Aucune clé API Hugging Face configurée. Ouvre ⚙ Paramètres pour l'ajouter."

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    convo = list(messages)

    for _ in range(max_tool_rounds):
        payload = {
            "model": model,
            "messages": convo,
            "max_tokens": 700,
            "temperature": 0.5,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=timeout)
        except requests.exceptions.Timeout:
            return False, "Le serveur Hugging Face met trop de temps à répondre. Réessaie."
        except requests.exceptions.RequestException as e:
            return False, f"Erreur de connexion : {e}"

        if resp.status_code == 401:
            return False, "Clé API invalide ou expirée. Vérifie ton token dans ⚙ Paramètres."
        elif resp.status_code == 404:
            return False, (
                f"Modèle '{model}' introuvable via Inference Providers. "
                "Essaie un autre identifiant de modèle dans ⚙ Paramètres."
            )
        elif resp.status_code == 429:
            return False, "Limite de requêtes atteinte pour le moment. Réessaie dans un instant."
        elif resp.status_code != 200:
            return False, f"Erreur API Hugging Face ({resp.status_code}) : {resp.text[:200]}"

        try:
            data = resp.json()
            choice_msg = data["choices"][0]["message"]
        except (KeyError, IndexError, ValueError):
            return False, "Réponse inattendue de l'API Hugging Face."

        tool_calls = choice_msg.get("tool_calls")
        if tool_calls and tool_executor:
            convo.append(choice_msg)
            for call in tool_calls:
                fn = call.get("function", {})
                fn_name = fn.get("name", "")
                try:
                    fn_args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    fn_args = {}
                result = tool_executor(fn_name, fn_args)
                convo.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", fn_name),
                    "name": fn_name,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue  # on redonne la main au modèle avec les résultats des outils

        content = (choice_msg.get("content") or "").strip()
        return True, content or "(réponse vide du modèle)"

    return False, "ModI a effectué plusieurs actions mais n'a pas réussi à conclure. Réessaie en reformulant."
