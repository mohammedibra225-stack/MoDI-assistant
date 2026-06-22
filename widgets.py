"""Widgets visuels réutilisables : orbe holographique animé, égaliseur,
texte en dégradé de couleur pour le titre.
"""

import math
import random
import tkinter as tk
import customtkinter as ctk

from theme import THEME


def lerp_color(c1, c2, t):
    """Interpole entre deux couleurs hexadécimales (#rrggbb)."""
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def build_gradient_label_row(parent, text, font, color_start, color_end):
    """Affiche un texte lettre par lettre avec un dégradé de couleur."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    n = max(len(text) - 1, 1)
    for i, ch in enumerate(text):
        color = lerp_color(color_start, color_end, i / n)
        lbl = ctk.CTkLabel(row, text=ch, font=font, text_color=color)
        lbl.pack(side="left", padx=1)
    return row


class HudOrb(ctk.CTkFrame):
    """Anneau holographique animé façon réacteur ARC / HUD Iron Man."""

    def __init__(self, parent, size=200, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.size = size
        self.cx = size / 2
        self.cy = size / 2
        self.state = "idle"
        self.angle1 = 0.0
        self.angle2 = 0.0
        self.angle3 = 0.0
        self.pulse_t = 0.0

        self.canvas = tk.Canvas(self, width=size, height=size, bg=THEME["panel"], highlightthickness=0)
        self.canvas.pack()
        self._build_items()
        self._animate()

    def _build_items(self):
        r1, r2, r3 = self.size * 0.46, self.size * 0.36, self.size * 0.27

        self.halo = self.canvas.create_oval(
            self.cx - r1 - 6, self.cy - r1 - 6, self.cx + r1 + 6, self.cy + r1 + 6,
            outline=THEME["border"], width=1,
        )
        self.arc_outer = self.canvas.create_arc(
            self.cx - r1, self.cy - r1, self.cx + r1, self.cy + r1,
            start=0, extent=110, style="arc", outline=THEME["cyan"], width=3,
        )
        self.arc_mid = self.canvas.create_arc(
            self.cx - r2, self.cy - r2, self.cx + r2, self.cy + r2,
            start=40, extent=80, style="arc", outline=THEME["violet"], width=2,
        )
        self.arc_inner = self.canvas.create_arc(
            self.cx - r3, self.cy - r3, self.cx + r3, self.cy + r3,
            start=200, extent=140, style="arc", outline=THEME["white"], width=1,
        )
        self.core_glow = self.canvas.create_oval(
            self.cx - 30, self.cy - 30, self.cx + 30, self.cy + 30,
            fill=THEME["panel_alt"], outline="",
        )
        self.core = self.canvas.create_oval(
            self.cx - 18, self.cy - 18, self.cx + 18, self.cy + 18,
            fill=THEME["cyan_dim"], outline=THEME["cyan"], width=2,
        )

    def set_state(self, state):
        self.state = state

    def _animate(self):
        speed = {"idle": 0.9, "listening": 3.4, "speaking": 2.3}.get(self.state, 0.9)
        self.angle1 = (self.angle1 + speed) % 360
        self.angle2 = (self.angle2 - speed * 1.3) % 360
        self.angle3 = (self.angle3 + speed * 0.7) % 360
        self.canvas.itemconfig(self.arc_outer, start=self.angle1)
        self.canvas.itemconfig(self.arc_mid, start=self.angle2)
        self.canvas.itemconfig(self.arc_inner, start=self.angle3)

        self.pulse_t += 0.12 if self.state != "idle" else 0.05
        pulse = (math.sin(self.pulse_t) + 1) / 2
        base_r = 16 if self.state != "idle" else 14
        r = base_r + pulse * (10 if self.state != "idle" else 5)
        self.canvas.coords(self.core, self.cx - r, self.cy - r, self.cx + r, self.cy + r)
        glow_r = r + 14
        self.canvas.coords(
            self.core_glow, self.cx - glow_r, self.cy - glow_r, self.cx + glow_r, self.cy + glow_r
        )

        colors = {
            "idle": (THEME["cyan"], THEME["cyan_dim"]),
            "listening": (THEME["red"], "#7a1530"),
            "speaking": (THEME["cyan"], THEME["cyan_dim"]),
        }
        outline_c, fill_c = colors.get(self.state, colors["idle"])
        self.canvas.itemconfig(self.core, outline=outline_c, fill=fill_c)
        self.canvas.itemconfig(self.arc_outer, outline=outline_c)

        self.after(40, self._animate)


class Equalizer(ctk.CTkFrame):
    """Petite barre d'égaliseur animée (réagit à l'état d'écoute/réponse)."""

    def __init__(self, parent, bars=14, width=200, height=46, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.n = bars
        self.w = width
        self.h = height
        self.state = "idle"
        self.heights = [4.0] * bars

        self.canvas = tk.Canvas(self, width=width, height=height, bg=THEME["panel"], highlightthickness=0)
        self.canvas.pack()

        gap = 4
        self.bw = (width - gap * (bars - 1)) / bars
        self.gap = gap
        self.bar_ids = []
        for i in range(bars):
            x0 = i * (self.bw + gap)
            y0 = height - 4
            bar = self.canvas.create_rectangle(x0, y0, x0 + self.bw, y0 - 4, fill=THEME["cyan_dim"], outline="")
            self.bar_ids.append(bar)

        self._animate()

    def set_state(self, state):
        self.state = state

    def _animate(self):
        color = {"idle": THEME["cyan_dim"], "listening": THEME["red"], "speaking": THEME["cyan"]}.get(
            self.state, THEME["cyan_dim"]
        )
        for i, bar in enumerate(self.bar_ids):
            target = random.uniform(2, self.h - 6) if self.state != "idle" else random.uniform(2, 6)
            self.heights[i] += (target - self.heights[i]) * 0.4
            x0 = i * (self.bw + self.gap)
            y0 = self.h - 4
            self.canvas.coords(bar, x0, y0, x0 + self.bw, y0 - self.heights[i])
            self.canvas.itemconfig(bar, fill=color)
        self.after(80, self._animate)
