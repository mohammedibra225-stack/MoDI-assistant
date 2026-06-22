"""Outils fichiers que ModI peut utiliser : chercher, ouvrir, lire, écrire,
supprimer. Découplé de l'interface graphique via un callback de confirmation,
fourni par gui.py (qui sait afficher une fenêtre de confirmation).
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

COMMON_FOLDERS = {
    "bureau": "Desktop", "desktop": "Desktop",
    "telechargements": "Downloads", "téléchargements": "Downloads", "downloads": "Downloads",
    "documents": "Documents",
    "images": "Pictures", "photos": "Pictures", "pictures": "Pictures",
    "musique": "Music", "music": "Music",
    "videos": "Videos", "vidéos": "Videos",
}


class FileTools:
    """Regroupe les actions fichiers utilisables par le modèle IA.

    confirm_callback(titre, message) -> bool : doit afficher une confirmation
    à l'utilisateur (bloquant) et renvoyer True/False. L'interface (gui.py)
    fournit cette fonction ; ce module ne connaît rien de tkinter.
    """

    def __init__(self, confirm_callback):
        self.confirm = confirm_callback

    # ----- Résolution de dossier (Bureau, Documents...) ---------------------
    def resolve_folder(self, dossier):
        if not dossier:
            return Path.home()
        key = dossier.strip().lower()
        mapped = COMMON_FOLDERS.get(key)
        if mapped:
            candidate = Path.home() / mapped
            if candidate.exists():
                return candidate
        candidate = Path(dossier).expanduser()
        if candidate.exists():
            return candidate
        return Path.home()

    # ----- Recherche ----------------------------------------------------------
    def search_files(self, nom, dossier=None):
        root = self.resolve_folder(dossier)
        nom_l = (nom or "").lower()
        results = []
        scanned = 0
        try:
            for p in root.rglob("*"):
                scanned += 1
                if scanned > 50000 or len(results) >= 15:
                    break
                if p.is_file() and nom_l in p.name.lower():
                    results.append(str(p))
        except Exception as e:
            return {"erreur": str(e)}
        return {"dossier_recherche": str(root), "resultats": results, "nombre_trouve": len(results)}

    # ----- Ouverture ------------------------------------------------------------
    def open_file(self, chemin):
        if not chemin:
            return {"erreur": "Aucun chemin fourni."}
        p = Path(chemin).expanduser()
        if not p.exists():
            return {"erreur": f"Le fichier '{chemin}' n'existe pas."}
        try:
            if os.name == "nt":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)], check=False)
            else:
                subprocess.run(["xdg-open", str(p)], check=False)
            return {"succes": True, "chemin": str(p)}
        except Exception as e:
            return {"erreur": str(e)}

    # ----- Lecture --------------------------------------------------------------
    def read_file(self, chemin, max_chars=4000):
        if not chemin:
            return {"erreur": "Aucun chemin fourni."}
        p = Path(chemin).expanduser()
        if not p.exists() or not p.is_file():
            return {"erreur": f"Le fichier '{chemin}' n'existe pas."}
        try:
            contenu = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"erreur": "Ce fichier semble binaire (image, PDF, etc.) — utilise ouvrir_fichier plutôt que lire_fichier."}
        except Exception as e:
            return {"erreur": f"Impossible de lire ce fichier : {e}"}
        tronque = len(contenu) > max_chars
        return {"chemin": str(p), "contenu": contenu[:max_chars], "tronque": tronque}

    # ----- Écriture / ajout -------------------------------------------------------
    def write_file(self, chemin, contenu, mode="remplacer"):
        if not chemin:
            return {"erreur": "Aucun chemin fourni."}
        p = Path(chemin).expanduser()
        mode = mode if mode in ("remplacer", "ajouter") else "remplacer"

        if mode == "remplacer" and p.exists() and p.stat().st_size > 0:
            confirmed = self.confirm(
                "Confirmer le remplacement",
                f"ModI veut remplacer tout le contenu de :\n{p}\n\nConfirmer ?",
            )
            if not confirmed:
                return {"annule": True, "message": "Modification annulée par l'utilisateur."}

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if mode == "ajouter":
                with open(p, "a", encoding="utf-8") as f:
                    f.write(contenu or "")
            else:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(contenu or "")
            return {"succes": True, "chemin": str(p), "mode": mode}
        except Exception as e:
            return {"erreur": str(e)}

    # ----- Suppression (corbeille locale, récupérable) ----------------------------
    def delete_file(self, chemin):
        if not chemin:
            return {"erreur": "Aucun chemin fourni."}
        p = Path(chemin).expanduser()
        if not p.exists():
            return {"erreur": f"Le fichier '{chemin}' n'existe pas."}

        confirmed = self.confirm(
            "Confirmer la suppression",
            f"ModI veut supprimer :\n{p}\n\n(Le fichier sera déplacé dans une corbeille récupérable.)\n\nConfirmer ?",
        )
        if not confirmed:
            return {"annule": True, "message": "Suppression annulée par l'utilisateur."}

        try:
            trash_dir = Path.home() / ".modi_corbeille"
            trash_dir.mkdir(exist_ok=True)
            destination = trash_dir / p.name
            counter = 1
            while destination.exists():
                destination = trash_dir / f"{p.stem}_{counter}{p.suffix}"
                counter += 1
            shutil.move(str(p), str(destination))
            return {"succes": True, "deplace_vers": str(destination), "message": "Fichier déplacé dans la corbeille ModI (récupérable)."}
        except Exception as e:
            return {"erreur": str(e)}

    # ----- Dispatcher utilisé par brain.ask_modi_brain --------------------------
    def execute(self, name, args):
        try:
            if name == "chercher_fichier":
                return self.search_files(args.get("nom", ""), args.get("dossier"))
            elif name == "ouvrir_fichier":
                return self.open_file(args.get("chemin"))
            elif name == "lire_fichier":
                return self.read_file(args.get("chemin"))
            elif name == "ecrire_fichier":
                return self.write_file(args.get("chemin"), args.get("contenu", ""), args.get("mode", "remplacer"))
            elif name == "supprimer_fichier":
                return self.delete_file(args.get("chemin"))
            else:
                return {"erreur": f"Outil inconnu : {name}"}
        except Exception as e:
            return {"erreur": str(e)}
