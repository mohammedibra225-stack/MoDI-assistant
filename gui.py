"""Interface principale de ModI : assemble le thème, la configuration,
le cerveau IA et les outils fichiers dans une fenêtre customtkinter.
"""

import os
import threading
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import pyttsx3
import speech_recognition as sr

from theme import THEME, FONT_TITLE, FONT_SUB, FONT_UI, FONT_UI_BOLD, FONT_MONO
from config import load_config, save_config, DEFAULT_CONFIG
from brain import ask_modi_brain, TOOLS_SPEC, MAX_HISTORY_MESSAGES
from file_tools import FileTools
from widgets import HudOrb, Equalizer, build_gradient_label_row

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ModIGUI:
    def __init__(self):
        self.cfg = load_config()
        self.hf_token = os.environ.get("HF_TOKEN", "") or self.cfg.get("hf_token", "")
        self.hf_model = self.cfg.get("hf_model", DEFAULT_CONFIG["hf_model"])
        self.tools = FileTools(confirm_callback=self.confirm_dialog_blocking)

        self.window = ctk.CTk()
        self.window.title("ModI — Assistant Personnel")
        self.window.geometry("900x680")
        self.window.resizable(False, False)
        self.window.configure(fg_color=THEME["bg"])

        try:
            self.window.iconbitmap("modi_icon.ico")
        except Exception:
            pass

        self.is_listening = False
        self.is_speaking = False
        self.history = []  # mémoire de conversation envoyée au modèle

        self.engine = pyttsx3.init()
        self.setup_voice()

        self.recognizer = sr.Recognizer()
        try:
            self.microphone = sr.Microphone()
        except Exception:
            self.microphone = None

        self.create_widgets()
        self._set_status("idle")

        if not self.hf_token:
            self.add_message(
                "Système",
                "Aucune clé API Hugging Face détectée. Ouvre ⚙ Paramètres pour l'ajouter "
                "et activer le cerveau IA de ModI.",
                kind="system",
            )

    # ----- Voix -----------------------------------------------------------
    def setup_voice(self):
        try:
            voices = self.engine.getProperty("voices")
            for voice in voices:
                if "french" in voice.name.lower():
                    self.engine.setProperty("voice", voice.id)
                    break
        except Exception:
            pass
        self.engine.setProperty("rate", self.cfg.get("voice_rate", 160))
        self.engine.setProperty("volume", self.cfg.get("voice_volume", 90) / 100)

    # ----- Construction de l'interface -------------------------------------
    def create_widgets(self):
        outer = ctk.CTkFrame(self.window, fg_color=THEME["bg"])
        outer.pack(fill="both", expand=True)

        # ---- En-tête ----
        header = ctk.CTkFrame(outer, fg_color=THEME["bg"])
        header.pack(fill="x", padx=24, pady=(20, 6))

        title_row = build_gradient_label_row(header, "M o D I", FONT_TITLE, THEME["cyan"], THEME["violet"])
        title_row.pack(anchor="center")

        ctk.CTkLabel(
            header, text="ModI — Assistant Personnel", font=FONT_SUB, text_color=THEME["grey"]
        ).pack(anchor="center", pady=(2, 10))

        status_bar = ctk.CTkFrame(
            header, fg_color=THEME["panel"], corner_radius=20, border_width=1, border_color=THEME["border"]
        )
        status_bar.pack(anchor="center")

        self.status_dot = ctk.CTkLabel(status_bar, text="●", font=("Segoe UI", 14), text_color=THEME["green"])
        self.status_dot.pack(side="left", padx=(16, 4), pady=6)

        self.status_label = ctk.CTkLabel(status_bar, text="En attente", font=FONT_UI_BOLD, text_color=THEME["white"])
        self.status_label.pack(side="left", padx=(0, 16), pady=6)

        self.time_label = ctk.CTkLabel(status_bar, text="", font=FONT_MONO, text_color=THEME["cyan"])
        self.time_label.pack(side="left", padx=(0, 16), pady=6)
        self.update_time()

        # ---- Corps : HUD à gauche, conversation à droite ----
        body = ctk.CTkFrame(outer, fg_color=THEME["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=10)
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(
            body, fg_color=THEME["panel"], corner_radius=18, border_width=1, border_color=THEME["border"]
        )
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 14))

        self.orb = HudOrb(left_panel, size=200)
        self.orb.pack(padx=20, pady=(28, 10))

        self.eq = Equalizer(left_panel, bars=14, width=200, height=46)
        self.eq.pack(padx=20, pady=(0, 18))

        ctk.CTkLabel(
            left_panel,
            text="Parle librement,\npas besoin de dire « ModI »",
            font=("Segoe UI", 11),
            text_color=THEME["grey"],
            justify="center",
        ).pack(padx=20, pady=(0, 26))

        right_panel = ctk.CTkFrame(
            body, fg_color=THEME["panel"], corner_radius=18, border_width=1, border_color=THEME["border"]
        )
        right_panel.grid(row=0, column=1, sticky="nsew")

        self.conversation_frame = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.conversation_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ---- Zone de saisie ----
        input_row = ctk.CTkFrame(outer, fg_color=THEME["bg"])
        input_row.pack(fill="x", padx=24, pady=(4, 6))

        self.listen_button = ctk.CTkButton(
            input_row, text="🎤 Parler", command=self.toggle_listening,
            font=FONT_UI_BOLD, height=42, width=120,
            fg_color=THEME["cyan"], hover_color=THEME["cyan_dim"], text_color="#031018",
            corner_radius=12,
        )
        self.listen_button.pack(side="left", padx=(0, 10))

        self.text_input = ctk.CTkEntry(
            input_row, placeholder_text="Écris ta commande ici…", font=FONT_UI, height=42,
            corner_radius=12, fg_color=THEME["panel"], border_color=THEME["border"],
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.text_input.bind("<Return>", self.send_text)

        self.send_button = ctk.CTkButton(
            input_row, text="➤", command=self.send_text, font=("Segoe UI", 16, "bold"),
            height=42, width=50, fg_color=THEME["violet"], hover_color="#6d28d9", corner_radius=12,
        )
        self.send_button.pack(side="left")

        # ---- Boutons rapides ----
        quick_row = ctk.CTkFrame(outer, fg_color=THEME["bg"])
        quick_row.pack(fill="x", padx=24, pady=(0, 18))

        actions = [
            ("🌐 Google", lambda: self.open_website("google.com")),
            ("▶ YouTube", lambda: self.open_website("youtube.com")),
            ("📂 Ouvrir fichier", self.open_file),
            ("🗑 Effacer", self.clear_conversation),
            ("⚙ Paramètres", self.show_settings),
        ]
        for text, cmd in actions:
            ctk.CTkButton(
                quick_row, text=text, command=cmd, font=("Segoe UI", 11), height=34,
                fg_color=THEME["panel_alt"], hover_color=THEME["border"], corner_radius=10,
            ).pack(side="left", padx=(0, 8))

    def update_time(self):
        self.time_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.window.after(1000, self.update_time)

    # ----- Statut global (HUD + égaliseur + pastille) ----------------------
    def _set_status(self, mode):
        labels = {
            "idle": ("En attente", THEME["green"]),
            "listening": ("Écoute en cours…", THEME["red"]),
            "thinking": ("ModI réfléchit…", THEME["violet"]),
            "speaking": ("ModI parle…", THEME["cyan"]),
        }
        text, color = labels.get(mode, labels["idle"])
        self.status_label.configure(text=text)
        self.status_dot.configure(text_color=color)

        orb_state = "listening" if mode == "listening" else ("speaking" if mode in ("speaking", "thinking") else "idle")
        self.orb.set_state(orb_state)
        self.eq.set_state(orb_state)

    # ----- Écoute vocale -----------------------------------------------------
    def toggle_listening(self):
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        self.is_listening = True
        self.listen_button.configure(text="⏹ Arrêter", fg_color=THEME["red"], hover_color="#b3324a")
        self._set_status("listening")
        threading.Thread(target=self.listen_loop, daemon=True).start()

    def stop_listening(self):
        self.is_listening = False
        self.listen_button.configure(text="🎤 Parler", fg_color=THEME["cyan"], hover_color=THEME["cyan_dim"])
        self._set_status("idle")

    def listen_loop(self):
        if not self.microphone:
            self.window.after(0, lambda: self.add_message("Système", "Microphone non détecté.", kind="system"))
            self.window.after(0, self.stop_listening)
            return

        with self.microphone as source:
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
            except Exception:
                pass

            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=6)
                    text = self.recognizer.recognize_google(audio, language="fr-FR")
                    if text:
                        # Plus besoin de dire "ModI" : on traite directement la phrase.
                        self.window.after(0, self.handle_user_text, text)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except Exception:
                    continue

    # ----- Saisie texte -------------------------------------------------------
    def send_text(self, event=None):
        text = self.text_input.get()
        if text.strip():
            self.text_input.delete(0, "end")
            self.handle_user_text(text)

    # ----- Pipeline de traitement (texte ou voix) ------------------------------
    def handle_user_text(self, text):
        text = text.strip()
        if not text:
            return

        self.add_message("Vous", text, kind="user")
        self.history.append({"role": "user", "content": text})

        local_reply = self.try_local_command(text)
        if local_reply is not None:
            self.add_message("ModI", local_reply, kind="modi")
            self.history.append({"role": "assistant", "content": local_reply})
            self.speak(local_reply)
            return

        self._set_status("thinking")
        _, think_label = self.add_message("ModI", "Réflexion en cours.", kind="modi")
        think_label._thinking_done = False

        def animate(n=0):
            if getattr(think_label, "_thinking_done", False):
                return
            dots = "." * (1 + n % 3)
            try:
                think_label.configure(text=f"Réflexion en cours{dots}")
            except Exception:
                return
            self.window.after(400, animate, n + 1)

        animate()

        threading.Thread(target=self._ask_brain_thread, args=(think_label,), daemon=True).start()

    def try_local_command(self, text):
        """Quelques raccourcis traités localement (rapides, pas besoin du modèle IA)."""
        t = text.lower()
        if "quelle heure" in t or t.strip() == "heure":
            return f"Il est {datetime.now().strftime('%H:%M')}."
        if "quelle date" in t or "quel jour" in t:
            return f"Nous sommes le {datetime.now().strftime('%d/%m/%Y')}."
        if "ouvre google" in t or t.strip() == "google":
            webbrowser.open("https://google.com")
            return "J'ouvre Google."
        if "ouvre youtube" in t or t.strip() == "youtube":
            webbrowser.open("https://youtube.com")
            return "J'ouvre YouTube."
        if "ouvre un fichier" in t or "ouvrir un fichier" in t or "ouvre fichier" in t or "ouvrir fichier" in t:
            self.window.after(0, self.open_file)
            return "D'accord, choisis le fichier que tu veux ouvrir."
        if "arrête" in t or t.strip() == "stop":
            if self.is_listening:
                self.window.after(0, self.stop_listening)
            return "D'accord, je me mets en pause."
        return None

    def _ask_brain_thread(self, think_label):
        messages = [{"role": "system", "content": self.cfg.get("system_prompt", DEFAULT_CONFIG["system_prompt"])}]
        messages.extend(self.history[-MAX_HISTORY_MESSAGES:])
        success, reply = ask_modi_brain(
            messages, self.hf_token, self.hf_model,
            tool_executor=self.tools.execute, tools=TOOLS_SPEC,
        )
        self.window.after(0, self._on_brain_response, think_label, success, reply)

    def _on_brain_response(self, think_label, success, reply):
        think_label._thinking_done = True
        try:
            think_label.configure(text=reply)
        except Exception:
            pass

        if success:
            self.history.append({"role": "assistant", "content": reply})

        self.conversation_frame.update_idletasks()
        try:
            self.conversation_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

        self.speak(reply)

    # ----- Confirmation bloquante (utilisée par file_tools.FileTools) ----------
    def confirm_dialog_blocking(self, title, message):
        """Affiche une fenêtre de confirmation et bloque le thread appelant
        jusqu'à la réponse de l'utilisateur (ou 60s de timeout = refus)."""
        result = {"value": False}
        event = threading.Event()

        def show():
            win = ctk.CTkToplevel(self.window)
            win.title(title)
            win.geometry("440x200")
            win.configure(fg_color=THEME["bg"])
            win.attributes("-topmost", True)
            win.grab_set()

            ctk.CTkLabel(
                win, text=message, font=FONT_UI, text_color=THEME["white"],
                wraplength=390, justify="left",
            ).pack(padx=20, pady=20)

            btn_row = ctk.CTkFrame(win, fg_color="transparent")
            btn_row.pack(pady=10)

            def yes():
                result["value"] = True
                win.destroy()
                event.set()

            def no():
                result["value"] = False
                win.destroy()
                event.set()

            ctk.CTkButton(btn_row, text="✅ Confirmer", fg_color=THEME["red"], hover_color="#b3324a", command=yes).pack(side="left", padx=10)
            ctk.CTkButton(btn_row, text="❌ Annuler", fg_color=THEME["panel_alt"], hover_color=THEME["border"], command=no).pack(side="left", padx=10)

        self.window.after(0, show)
        event.wait(timeout=60)
        return result["value"]

    # ----- Affichage des messages -------------------------------------------
    def add_message(self, sender, text, kind="modi"):
        row = ctk.CTkFrame(self.conversation_frame, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=6)

        styles = {
            "user": (THEME["panel_alt"], THEME["violet"], "e"),
            "system": (THEME["panel"], THEME["amber"], "w"),
            "modi": (THEME["panel"], THEME["cyan"], "w"),
        }
        bg, accent, anchor = styles.get(kind, styles["modi"])

        bubble = ctk.CTkFrame(row, fg_color=bg, corner_radius=14, border_width=1, border_color=accent)
        bubble.pack(anchor=anchor, padx=4)

        ctk.CTkLabel(
            bubble, text=f"{sender}  ·  {datetime.now().strftime('%H:%M')}",
            font=("Segoe UI", 11, "bold"), text_color=accent,
        ).pack(anchor="w", padx=14, pady=(8, 0))

        msg_label = ctk.CTkLabel(
            bubble, text=text, font=("Segoe UI", 13), text_color=THEME["white"],
            wraplength=520, justify="left",
        )
        msg_label.pack(anchor="w", padx=14, pady=(2, 10))

        self.conversation_frame.update_idletasks()
        try:
            self.conversation_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

        return bubble, msg_label

    def clear_conversation(self):
        for widget in self.conversation_frame.winfo_children():
            widget.destroy()
        self.history = []

    def open_file(self):
        path = filedialog.askopenfilename(
            initialdir=os.path.expanduser("~"),
            title="Sélectionner un fichier",
            filetypes=[("Tous les fichiers", "*.*")],
        )
        if not path:
            return
        result = self.tools.open_file(path)
        if result.get("succes"):
            self.add_message("ModI", f"Fichier ouvert : {path}", kind="modi")
        else:
            self.add_message("ModI", f"Fichier sélectionné : {path} ({result.get('erreur', 'ouverture impossible')})", kind="modi")

    def open_website(self, url):
        webbrowser.open(f"https://{url}")
        self.add_message("ModI", f"Ouverture de {url}…", kind="modi")

    # ----- Synthèse vocale ----------------------------------------------------
    def speak(self, text):
        if self.is_speaking:
            return
        self.is_speaking = True
        self._set_status("speaking")

        def _run():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception:
                pass
            finally:
                self.is_speaking = False
                self.window.after(0, self._after_speak)

        threading.Thread(target=_run, daemon=True).start()

    def _after_speak(self):
        self._set_status("listening" if self.is_listening else "idle")

    # ----- Fenêtre des paramètres -----------------------------------------------
    def show_settings(self):
        win = ctk.CTkToplevel(self.window)
        win.title("Paramètres ModI")
        win.geometry("460x660")
        win.configure(fg_color=THEME["bg"])
        win.grab_set()

        ctk.CTkLabel(win, text="⚙ Paramètres", font=("Segoe UI", 20, "bold"), text_color=THEME["cyan"]).pack(
            pady=(20, 10)
        )

        ctk.CTkLabel(
            win,
            text=(
                "Pour activer le cerveau IA de ModI : crée un compte sur\n"
                "huggingface.co -> Settings -> Access Tokens -> New token\n"
                "(type 'Fine-grained', permission 'Make calls to Inference\n"
                "Providers'), puis colle le token ci-dessous.\n"
                "Modèle conseillé pour l'accès fichiers : openai/gpt-oss-120b"
            ),
            font=("Segoe UI", 11),
            text_color=THEME["grey"],
            justify="left",
        ).pack(padx=20, pady=(0, 15))

        ctk.CTkLabel(win, text="Clé API Hugging Face (HF_TOKEN)", font=FONT_UI_BOLD, text_color=THEME["white"]).pack(
            anchor="w", padx=20
        )
        token_placeholder = "•••• (clé déjà enregistrée — laisse vide pour la conserver)" if self.hf_token else "hf_xxxxxxxxxxxxxxxx"
        token_entry = ctk.CTkEntry(win, placeholder_text=token_placeholder, show="•", width=400)
        token_entry.pack(padx=20, pady=(4, 14))

        ctk.CTkLabel(win, text="Modèle (Inference Providers)", font=FONT_UI_BOLD, text_color=THEME["white"]).pack(
            anchor="w", padx=20
        )
        model_entry = ctk.CTkEntry(win, width=400)
        model_entry.insert(0, self.hf_model)
        model_entry.pack(padx=20, pady=(4, 14))

        test_result = ctk.CTkLabel(
            win, text="", font=("Segoe UI", 11), text_color=THEME["grey"], wraplength=400, justify="left"
        )

        def do_test():
            token = token_entry.get().strip() or self.hf_token
            model = model_entry.get().strip() or self.hf_model
            test_result.configure(text="Test en cours…", text_color=THEME["grey"])

            def _t():
                success, reply = ask_modi_brain(
                    [{"role": "user", "content": "Réponds juste 'OK' pour tester la connexion."}],
                    token, model, timeout=20,
                )

                def _update():
                    if success:
                        test_result.configure(
                            text=f"✅ Connexion réussie. Réponse du modèle : {reply[:120]}",
                            text_color=THEME["green"],
                        )
                    else:
                        test_result.configure(text=f"❌ {reply}", text_color=THEME["red"])

                win.after(0, _update)

            threading.Thread(target=_t, daemon=True).start()

        ctk.CTkButton(
            win, text="🔌 Tester la connexion", command=do_test, fg_color=THEME["violet"], hover_color="#6d28d9"
        ).pack(padx=20, pady=(0, 6))
        test_result.pack(padx=20, pady=(0, 14))

        ctk.CTkLabel(win, text="Vitesse de la voix", font=FONT_UI_BOLD, text_color=THEME["white"]).pack(
            anchor="w", padx=20
        )
        rate_slider = ctk.CTkSlider(win, from_=80, to=260)
        rate_slider.set(self.cfg.get("voice_rate", 160))
        rate_slider.pack(padx=20, pady=(4, 14), fill="x")

        ctk.CTkLabel(win, text="Volume de la voix", font=FONT_UI_BOLD, text_color=THEME["white"]).pack(
            anchor="w", padx=20
        )
        volume_slider = ctk.CTkSlider(win, from_=0, to=100)
        volume_slider.set(self.cfg.get("voice_volume", 90))
        volume_slider.pack(padx=20, pady=(4, 20), fill="x")

        def do_save():
            new_token = token_entry.get().strip()
            if new_token:
                self.hf_token = new_token
                self.cfg["hf_token"] = new_token

            new_model = model_entry.get().strip()
            if new_model:
                self.hf_model = new_model
                self.cfg["hf_model"] = new_model

            self.cfg["voice_rate"] = int(rate_slider.get())
            self.cfg["voice_volume"] = int(volume_slider.get())
            try:
                self.engine.setProperty("rate", self.cfg["voice_rate"])
                self.engine.setProperty("volume", self.cfg["voice_volume"] / 100)
            except Exception:
                pass

            ok = save_config(self.cfg)
            test_result.configure(
                text="💾 Paramètres enregistrés." if ok else "⚠ Impossible d'écrire le fichier de configuration.",
                text_color=THEME["green"] if ok else THEME["amber"],
            )

        ctk.CTkButton(
            win, text="💾 Enregistrer", command=do_save, fg_color=THEME["cyan"],
            hover_color=THEME["cyan_dim"], text_color="#031018",
        ).pack(pady=(0, 20))

    # ----- Lancement -------------------------------------------------------
    def run(self):
        welcome = (
            "Bonjour. Je suis ModI, prêt à t'écouter — clique sur 🎤 ou écris "
            "directement, plus besoin de dire mon nom avant de parler. "
            "Je peux aussi chercher, ouvrir, lire, écrire et supprimer des fichiers si tu me le demandes."
        )
        self.add_message("ModI", welcome, kind="modi")
        self.history.append({"role": "assistant", "content": welcome})
        self.window.mainloop()
