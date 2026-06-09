"""
AI Chat – ChatGPT & Claude
Starten : python ai_chat.py
Benötigt : pip install openai anthropic requests
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import json
import os

# ╔══════════════════════════════════════════════════════════╗
#  FARBEN  –  warmes Papier / Tinte Ästhetik
# ╚══════════════════════════════════════════════════════════╝
C = {
    "bg"          : "#F5F0E8",   # warmes Papier
    "sidebar"     : "#EDE7D9",   # leicht dunkler
    "panel"       : "#E8E1D0",   # Panel-Hintergrund
    "border"      : "#C8BEAA",   # Linie / Rahmen
    "border_soft" : "#DDD7C8",

    "ink"         : "#2C2416",   # Haupttext (fast Schwarz)
    "ink_mid"     : "#6B5E4A",   # Sekundärtext
    "ink_light"   : "#9C8E78",   # Placeholder / Hint

    # Akzent: tiefes Teal/Grün
    "accent"      : "#2E6B5E",
    "accent_hover": "#245549",
    "accent_light": "#D4EAE5",

    # Nutzer-Bubble: sanftes Terrakotta
    "user_bubble" : "#E8DDD0",
    "user_border" : "#C4B49A",

    # AI-Bubble: fast weiß
    "ai_bubble"   : "#FDFAF5",
    "ai_border"   : "#D8D0C0",

    # Fehler
    "error"       : "#8B2020",
    "error_bg"    : "#F5DADA",

    # Buttons – IMMER heller Hintergrund + dunkle Schrift
    "btn_bg"      : "#FDFAF5",
    "btn_fg"      : "#2C2416",
    "btn_hover"   : "#EDE7D9",
    "btn_border"  : "#C8BEAA",

    # Senden-Button – dunkel mit hellem Text
    "send_bg"     : "#2E6B5E",
    "send_fg"     : "#FDFAF5",
    "send_hover"  : "#245549",

    # Provider-Badges
    "gpt_badge"   : "#10A37F",   # OpenAI Grün
    "claude_badge": "#D4761A",   # Anthropic Orange
}

FONT_TITLE  = ("Georgia", 15, "bold")
FONT_HEADER = ("Georgia", 11)
FONT_BODY   = ("Georgia", 10)
FONT_SMALL  = ("Verdana", 8)
FONT_MONO   = ("Courier New", 9)
FONT_LABEL  = ("Verdana", 9, "bold")

PROVIDERS = {
    "ChatGPT (OpenAI)": {
        "model": "gpt-4o",
        "badge": "#10A37F",
        "short": "GPT",
    },
    "Claude (Anthropic)": {
        "model": "claude-opus-4-6",
        "badge": "#D4761A",
        "short": "Claude",
    },
}

MODELS = {
    "ChatGPT (OpenAI)": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "Claude (Anthropic)": [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    ],
}


# ╔══════════════════════════════════════════════════════════╗
#  API-CALLS
# ╚══════════════════════════════════════════════════════════╝

def call_openai(api_key, model, messages):
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(model=model, messages=messages, max_tokens=2048)
        return resp.choices[0].message.content
    except ImportError:
        pass
    import requests
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post("https://api.openai.com/v1/chat/completions",
                      headers=headers,
                      json={"model": model, "messages": messages, "max_tokens": 2048},
                      timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_anthropic(api_key, model, messages):
    sys_msgs  = [m for m in messages if m["role"] == "system"]
    chat_msgs = [m for m in messages if m["role"] != "system"]
    system    = sys_msgs[0]["content"] if sys_msgs else "You are a helpful assistant."
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(model=model, max_tokens=2048,
                                      system=system, messages=chat_msgs)
        return resp.content[0].text
    except ImportError:
        pass
    import requests
    headers = {"x-api-key": api_key,
               "anthropic-version": "2023-06-01",
               "Content-Type": "application/json"}
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers=headers,
                      json={"model": model, "max_tokens": 2048,
                            "system": system, "messages": chat_msgs},
                      timeout=60)
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def send_to_ai(provider, api_key, model, messages):
    if "OpenAI" in provider:
        return call_openai(api_key, model, messages)
    return call_anthropic(api_key, model, messages)


# ╔══════════════════════════════════════════════════════════╗
#  HILFSFUNKTIONEN  –  gestylte Widgets
# ╚══════════════════════════════════════════════════════════╝

def flat_button(parent, text, command, style="normal", width=None):
    """Erstellt einen flachen Button mit klar kontrastierenden Farben."""
    if style == "send":
        bg, fg, hov = C["send_bg"], C["send_fg"], C["send_hover"]
        font = ("Verdana", 9, "bold")
    elif style == "danger":
        bg, fg, hov = "#FDFAF5", C["error"], "#F5DADA"
        font = ("Verdana", 9)
    else:
        bg, fg, hov = C["btn_bg"], C["btn_fg"], C["btn_hover"]
        font = ("Verdana", 9)

    btn = tk.Button(parent, text=text, command=command,
                    bg=bg, fg=fg,
                    activebackground=hov, activeforeground=fg,
                    relief="flat", bd=0, font=font,
                    cursor="hand2", padx=10, pady=5,
                    highlightthickness=1,
                    highlightbackground=C["btn_border"],
                    highlightcolor=C["accent"])
    if width:
        btn.configure(width=width)
    return btn


# ╔══════════════════════════════════════════════════════════╗
#  HAUPT-APP
# ╚══════════════════════════════════════════════════════════╝

class AIChatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Chat")
        self.geometry("960x700")
        self.minsize(760, 520)
        self.configure(bg=C["bg"])

        self.history      = []
        self.system_prompt = "You are a helpful, concise assistant."
        self.settings     = self._load_settings()
        self.is_loading   = False

        self._build_ui()
        self._refresh_model_list()

    # ── Persistenz ───────────────────────────────────────────

    def _cfg_path(self):
        return os.path.join(os.path.expanduser("~"), ".aichat2_settings.json")

    def _load_settings(self):
        try:
            with open(self._cfg_path()) as f:
                return json.load(f)
        except Exception:
            return {"provider": "ChatGPT (OpenAI)", "api_keys": {}, "models": {}}

    def _save_settings(self):
        try:
            with open(self._cfg_path(), "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    # ── UI-Aufbau ────────────────────────────────────────────

    def _build_ui(self):
        # ═══ LINKE SIDEBAR ═══════════════════════════════════
        self.sidebar = tk.Frame(self, bg=C["sidebar"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo / Titel
        title_frame = tk.Frame(self.sidebar, bg=C["sidebar"], pady=18)
        title_frame.pack(fill="x")
        tk.Label(title_frame, text="✦ AI Chat",
                 bg=C["sidebar"], fg=C["ink"],
                 font=FONT_TITLE).pack()
        tk.Label(title_frame, text="Dein persönlicher KI-Assistent",
                 bg=C["sidebar"], fg=C["ink_light"],
                 font=FONT_SMALL, wraplength=190).pack(pady=(2, 0))

        # Trennlinie
        tk.Frame(self.sidebar, bg=C["border"], height=1).pack(fill="x", padx=16)

        # ─ Provider-Auswahl ─
        sec = tk.Frame(self.sidebar, bg=C["sidebar"], pady=14, padx=16)
        sec.pack(fill="x")
        tk.Label(sec, text="ANBIETER", bg=C["sidebar"], fg=C["ink_mid"],
                 font=FONT_SMALL).pack(anchor="w", pady=(0, 6))

        self.provider_var = tk.StringVar(value=self.settings.get("provider", "ChatGPT (OpenAI)"))
        for name in PROVIDERS:
            self._provider_radio(sec, name)

        tk.Frame(self.sidebar, bg=C["border"], height=1).pack(fill="x", padx=16)

        # ─ Modell ─
        mod_sec = tk.Frame(self.sidebar, bg=C["sidebar"], pady=14, padx=16)
        mod_sec.pack(fill="x")
        tk.Label(mod_sec, text="MODELL", bg=C["sidebar"], fg=C["ink_mid"],
                 font=FONT_SMALL).pack(anchor="w", pady=(0, 6))

        self.model_var = tk.StringVar()
        self.model_cb  = ttk.Combobox(mod_sec, textvariable=self.model_var,
                                       state="readonly", width=22)
        self.model_cb.pack(anchor="w")
        self._style_combobox()

        tk.Frame(self.sidebar, bg=C["border"], height=1).pack(fill="x", padx=16)

        # ─ Aktionen ─
        act_sec = tk.Frame(self.sidebar, bg=C["sidebar"], pady=14, padx=16)
        act_sec.pack(fill="x")
        tk.Label(act_sec, text="AKTIONEN", bg=C["sidebar"], fg=C["ink_mid"],
                 font=FONT_SMALL).pack(anchor="w", pady=(0, 8))

        flat_button(act_sec, "🔑  API-Keys verwalten", self._open_keys).pack(fill="x", pady=2)
        flat_button(act_sec, "📝  System-Prompt",      self._edit_system).pack(fill="x", pady=2)
        flat_button(act_sec, "🗑  Chat leeren",         self._new_chat,
                    style="danger").pack(fill="x", pady=(8, 2))

        # ─ Status-Info ─
        self.status_lbl = tk.Label(self.sidebar, text="",
                                    bg=C["sidebar"], fg=C["ink_mid"],
                                    font=FONT_SMALL, wraplength=190, justify="left")
        self.status_lbl.pack(side="bottom", padx=16, pady=12, anchor="w")

        # ─ Key-Indikator unten ─
        self.key_indicator = tk.Label(self.sidebar, text="",
                                       bg=C["sidebar"], fg=C["ink_light"],
                                       font=FONT_SMALL)
        self.key_indicator.pack(side="bottom", padx=16, anchor="w")
        self._update_key_indicator()

        self.provider_var.trace_add("write", lambda *_: self._on_provider_change())

        # ═══ HAUPTBEREICH ════════════════════════════════════
        main = tk.Frame(self, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)

        # ─ Chat-Bereich ─
        chat_wrapper = tk.Frame(main, bg=C["bg"])
        chat_wrapper.pack(fill="both", expand=True, padx=0, pady=0)

        self.canvas = tk.Canvas(chat_wrapper, bg=C["bg"], bd=0, highlightthickness=0)
        vsb = tk.Scrollbar(chat_wrapper, orient="vertical", command=self.canvas.yview)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.configure(yscrollcommand=vsb.set)

        self.msg_frame = tk.Frame(self.canvas, bg=C["bg"])
        self._cwin = self.canvas.create_window((0, 0), window=self.msg_frame, anchor="nw")
        self.msg_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                          lambda e: self.canvas.itemconfig(self._cwin, width=e.width))
        self.canvas.bind_all("<MouseWheel>",
                              lambda e: self.canvas.yview_scroll(-1*(e.delta//120), "units"))

        # ─ Trennlinie vor Eingabe ─
        tk.Frame(main, bg=C["border"], height=1).pack(fill="x")

        # ─ Eingabe-Leiste ─
        input_bar = tk.Frame(main, bg=C["panel"], pady=12, padx=14)
        input_bar.pack(fill="x")

        # Textfeld mit Rahmen-Frame
        entry_frame = tk.Frame(input_bar, bg=C["border"], padx=1, pady=1)
        entry_frame.pack(side="left", fill="both", expand=True)

        inner_entry = tk.Frame(entry_frame, bg=C["ai_bubble"])
        inner_entry.pack(fill="both", expand=True)

        self.input_txt = tk.Text(inner_entry, height=3,
                                  bg=C["ai_bubble"], fg=C["ink"],
                                  insertbackground=C["ink"],
                                  relief="flat", bd=0,
                                  font=FONT_BODY, wrap="word",
                                  padx=10, pady=8)
        self.input_txt.pack(fill="both", expand=True)
        self.input_txt.bind("<Return>",       self._on_enter)
        self.input_txt.bind("<Shift-Return>", lambda e: None)

        # Placeholder
        self._placeholder_active = False
        self._set_placeholder()
        self.input_txt.bind("<FocusIn>",  self._clear_placeholder)
        self.input_txt.bind("<FocusOut>", self._restore_placeholder)

        # Senden
        send_frame = tk.Frame(input_bar, bg=C["panel"])
        send_frame.pack(side="right", padx=(10, 4), anchor="center")

        send_btn = tk.Button(send_frame, text="Senden ↵",
                              command=self._send,
                              bg=C["send_bg"], fg=C["send_fg"],
                              activebackground=C["send_hover"],
                              activeforeground=C["send_fg"],
                              relief="flat", bd=0,
                              font=("Verdana", 10, "bold"),
                              cursor="hand2",
                              padx=18, pady=14,
                              highlightthickness=0)
        send_btn.pack()
        tk.Label(send_frame, text="Shift+↵ = neue Zeile",
                 bg=C["panel"], fg=C["ink_light"], font=FONT_SMALL).pack(pady=(5, 0))

    # ── Placeholder ──────────────────────────────────────────

    def _set_placeholder(self):
        self.input_txt.delete("1.0", "end")
        self.input_txt.insert("1.0", "Nachricht eingeben …")
        self.input_txt.configure(fg=C["ink_light"])
        self._placeholder_active = True

    def _clear_placeholder(self, _=None):
        if self._placeholder_active:
            self.input_txt.delete("1.0", "end")
            self.input_txt.configure(fg=C["ink"])
            self._placeholder_active = False

    def _restore_placeholder(self, _=None):
        if not self.input_txt.get("1.0", "end").strip():
            self._set_placeholder()

    # ── Combobox-Style ───────────────────────────────────────

    def _style_combobox(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TCombobox",
                     fieldbackground=C["btn_bg"],
                     background=C["btn_bg"],
                     foreground=C["ink"],
                     selectbackground=C["accent_light"],
                     selectforeground=C["ink"],
                     arrowcolor=C["ink_mid"],
                     bordercolor=C["border"],
                     lightcolor=C["border"],
                     darkcolor=C["border"])
        s.map("TCombobox",
              fieldbackground=[("readonly", C["btn_bg"])],
              foreground=[("readonly", C["ink"])])

    # ── Provider-Radio ───────────────────────────────────────

    def _provider_radio(self, parent, name):
        info  = PROVIDERS[name]
        frame = tk.Frame(parent, bg=C["sidebar"], cursor="hand2")
        frame.pack(fill="x", pady=2)

        badge = tk.Label(frame, text=info["short"], bg=info["badge"], fg="white",
                          font=("Verdana", 7, "bold"), padx=5, pady=2, width=6)
        badge.pack(side="left")

        lbl = tk.Label(frame, text=name.split(" ")[0],
                        bg=C["sidebar"], fg=C["ink"], font=FONT_BODY, padx=8)
        lbl.pack(side="left")

        # Aktiv-Markierung
        indicator = tk.Label(frame, text="◀", bg=C["sidebar"], fg=C["accent"],
                               font=FONT_SMALL)

        def select():
            self.provider_var.set(name)

        for w in (frame, badge, lbl, indicator):
            w.bind("<Button-1>", lambda e, n=name: (self.provider_var.set(n)))

        def refresh_indicator(*_):
            if self.provider_var.get() == name:
                indicator.pack(side="right", padx=4)
                frame.configure(bg=C["accent_light"])
                lbl.configure(bg=C["accent_light"])
                badge_frame_bg = C["accent_light"]
            else:
                indicator.pack_forget()
                frame.configure(bg=C["sidebar"])
                lbl.configure(bg=C["sidebar"])

        self.provider_var.trace_add("write", lambda *_: refresh_indicator())
        refresh_indicator()

    # ── Provider / Modell ────────────────────────────────────

    def _on_provider_change(self):
        prov = self.provider_var.get()
        self.settings["provider"] = prov
        self._save_settings()
        self._refresh_model_list()
        self._update_key_indicator()

    def _refresh_model_list(self):
        prov   = self.provider_var.get()
        models = MODELS.get(prov, [])
        self.model_cb.configure(values=models)
        saved  = self.settings.get("models", {}).get(prov)
        self.model_var.set(saved if saved in models else models[0])

    def _update_key_indicator(self):
        prov = self.provider_var.get()
        has  = bool(self.settings.get("api_keys", {}).get(prov, "").strip())
        self.key_indicator.configure(
            text="● API-Key gespeichert" if has else "○ Kein API-Key",
            fg=C["accent"] if has else C["error"])

    # ── Dialoge ──────────────────────────────────────────────

    def _open_keys(self):
        win = tk.Toplevel(self)
        win.title("API-Keys verwalten")
        win.geometry("500x300")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="API-Keys", bg=C["bg"], fg=C["ink"],
                 font=FONT_TITLE, pady=14).pack()
        tk.Label(win, text="Schlüssel werden lokal auf deinem Gerät gespeichert.",
                 bg=C["bg"], fg=C["ink_light"], font=FONT_SMALL).pack(pady=(0, 6))
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20)

        key_vars = {}
        for prov in PROVIDERS:
            row = tk.Frame(win, bg=C["bg"], pady=10, padx=24)
            row.pack(fill="x")
            info = PROVIDERS[prov]

            tk.Label(row, text=info["short"], bg=info["badge"], fg="white",
                      font=("Verdana", 8, "bold"), padx=6, pady=3, width=6).pack(side="left")
            tk.Label(row, text=prov, bg=C["bg"], fg=C["ink"],
                      font=FONT_BODY, width=18, anchor="w").pack(side="left", padx=10)

            var = tk.StringVar(value=self.settings.get("api_keys", {}).get(prov, ""))
            key_vars[prov] = var

            entry = tk.Entry(row, textvariable=var, show="●",
                              bg=C["ai_bubble"], fg=C["ink"],
                              insertbackground=C["ink"],
                              relief="flat", font=FONT_MONO, width=30,
                              highlightthickness=1,
                              highlightbackground=C["border"],
                              highlightcolor=C["accent"])
            entry.pack(side="left")

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(10, 0))

        btn_row = tk.Frame(win, bg=C["bg"], pady=12)
        btn_row.pack()

        def save_all():
            for p, v in key_vars.items():
                self.settings.setdefault("api_keys", {})[p] = v.get().strip()
            self._save_settings()
            self._update_key_indicator()
            self._show_status("API-Keys gespeichert ✓")
            win.destroy()

        # Speichern-Button: dunkel mit hellem Text
        tk.Button(btn_row, text="Speichern & Schließen",
                  command=save_all,
                  bg=C["send_bg"], fg=C["send_fg"],
                  activebackground=C["send_hover"], activeforeground=C["send_fg"],
                  relief="flat", bd=0,
                  font=("Verdana", 9, "bold"),
                  cursor="hand2", padx=16, pady=7,
                  highlightthickness=0).pack(side="left", padx=6)

        # Abbrechen-Button: hell mit dunklem Text
        tk.Button(btn_row, text="Abbrechen",
                  command=win.destroy,
                  bg=C["btn_bg"], fg=C["btn_fg"],
                  activebackground=C["btn_hover"], activeforeground=C["btn_fg"],
                  relief="flat", bd=0,
                  font=("Verdana", 9),
                  cursor="hand2", padx=16, pady=7,
                  highlightthickness=1,
                  highlightbackground=C["btn_border"]).pack(side="left", padx=6)

    def _edit_system(self):
        win = tk.Toplevel(self)
        win.title("System-Prompt")
        win.geometry("560x280")
        win.configure(bg=C["bg"])
        win.resizable(True, False)
        win.grab_set()

        tk.Label(win, text="System-Prompt", bg=C["bg"], fg=C["ink"],
                 font=FONT_TITLE, pady=14).pack()
        tk.Label(win, text="Legt fest, wie sich die KI verhält.",
                 bg=C["bg"], fg=C["ink_mid"], font=FONT_SMALL).pack()
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)

        entry_f = tk.Frame(win, bg=C["border"], padx=1, pady=1)
        entry_f.pack(fill="both", expand=True, padx=20)
        txt = tk.Text(entry_f, bg=C["ai_bubble"], fg=C["ink"],
                       insertbackground=C["ink"],
                       relief="flat", font=FONT_BODY, wrap="word",
                       padx=10, pady=8, height=6)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", self.system_prompt)

        def save():
            self.system_prompt = txt.get("1.0", "end").strip()
            self._show_status("System-Prompt aktualisiert ✓")
            win.destroy()

        btn_row = tk.Frame(win, bg=C["bg"], pady=10)
        btn_row.pack()
        flat_button(btn_row, "Speichern", save, style="send").pack(side="left", padx=4)
        flat_button(btn_row, "Abbrechen", win.destroy).pack(side="left", padx=4)

    def _new_chat(self):
        if not self.history:
            return
        if messagebox.askyesno("Chat leeren",
                                "Den gesamten Verlauf löschen?", parent=self):
            self.history.clear()
            for w in self.msg_frame.winfo_children():
                w.destroy()
            self._show_status("Neuer Chat gestartet.")

    # ── Status ───────────────────────────────────────────────

    def _show_status(self, msg):
        self.status_lbl.configure(text=msg)
        self.after(3000, lambda: self.status_lbl.configure(text=""))

    # ── Senden ───────────────────────────────────────────────

    def _on_enter(self, event):
        if not (event.state & 0x1):
            self._send()
            return "break"

    def _send(self):
        if self.is_loading:
            return
        # Placeholder wegräumen falls noch aktiv (z.B. bei Button-Klick ohne Fokus)
        if self._placeholder_active:
            self._clear_placeholder()

        text = self.input_txt.get("1.0", "end").strip()
        if not text:
            return

        prov    = self.provider_var.get()
        api_key = self.settings.get("api_keys", {}).get(prov, "").strip()
        if not api_key:
            messagebox.showwarning(
                "API-Key fehlt",
                f"Bitte zuerst den API-Key für {prov} eintragen.\n"
                "(Sidebar → API-Keys verwalten)",
                parent=self)
            return

        model = self.model_var.get()
        self.settings.setdefault("models", {})[prov] = model
        self._save_settings()

        self.input_txt.delete("1.0", "end")
        self._set_placeholder()

        self._add_bubble("user", text)
        self.history.append({"role": "user", "content": text})

        self.is_loading = True
        thinking = self._add_thinking()

        def worker():
            try:
                msgs  = [{"role": "system", "content": self.system_prompt}] + self.history
                reply = send_to_ai(prov, api_key, model, msgs)
                err   = None
            except Exception as e:
                reply = None
                err   = str(e)
            self.after(0, lambda: self._on_reply(thinking, prov, reply, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_reply(self, thinking, prov, reply, error):
        self.is_loading = False
        thinking.destroy()
        if error:
            self._add_bubble("error", f"Fehler: {error}")
        else:
            self._add_bubble("ai", reply, prov=prov)
            self.history.append({"role": "assistant", "content": reply})
        self._scroll_bottom()

    # ── Bubbles ──────────────────────────────────────────────

    def _add_bubble(self, role, text, prov=None):
        is_user  = role == "user"
        is_error = role == "error"

        outer = tk.Frame(self.msg_frame, bg=C["bg"], pady=6)
        outer.pack(fill="x", padx=20)

        if is_user:
            label     = "Du"
            label_fg  = C["ink_mid"]
            bub_bg    = C["user_bubble"]
            bub_bd    = C["user_border"]
            anchor    = "e"
        elif is_error:
            label     = "Fehler"
            label_fg  = C["error"]
            bub_bg    = C["error_bg"]
            bub_bd    = C["error"]
            anchor    = "w"
        else:
            info      = PROVIDERS.get(prov or "", {})
            label     = info.get("short", "KI")
            label_fg  = info.get("badge", C["ink_mid"])
            bub_bg    = C["ai_bubble"]
            bub_bd    = C["ai_border"]
            anchor    = "w"

        inner = tk.Frame(outer, bg=C["bg"])
        inner.pack(anchor=anchor)

        # Label oben
        tk.Label(inner, text=label, bg=C["bg"], fg=label_fg,
                 font=FONT_LABEL).pack(anchor=anchor, pady=(0, 2))

        # Bubble mit Rahmen
        bub_outer = tk.Frame(inner, bg=bub_bd, padx=1, pady=1)
        bub_outer.pack(anchor=anchor)
        bub = tk.Frame(bub_outer, bg=bub_bg)
        bub.pack()

        # Maximale Breite ~70% des Fensters
        wrap_px = max(300, int(self.winfo_width() * 0.62))

        txt_w = tk.Text(bub, bg=bub_bg, fg=C["ink"],
                         font=FONT_BODY, wrap="word",
                         relief="flat", bd=0,
                         padx=14, pady=10,
                         cursor="arrow",
                         width=int(wrap_px / 7.5),
                         height=1)
        txt_w.insert("1.0", text)
        txt_w.configure(state="disabled")
        txt_w.pack()

        # Höhe anpassen
        lines = text.count("\n") + 1
        extra = sum(max(0, len(l) // int(wrap_px / 7.5)) for l in text.splitlines())
        txt_w.configure(height=min(lines + extra, 50))

        self._scroll_bottom()
        return outer

    def _add_thinking(self):
        outer = tk.Frame(self.msg_frame, bg=C["bg"], pady=6)
        outer.pack(fill="x", padx=20)
        inner = tk.Frame(outer, bg=C["bg"])
        inner.pack(anchor="w")

        prov = self.provider_var.get()
        info = PROVIDERS.get(prov, {})
        tk.Label(inner, text=info.get("short", "KI"),
                 bg=C["bg"], fg=info.get("badge", C["ink_mid"]),
                 font=FONT_LABEL).pack(anchor="w", pady=(0, 2))

        bub_outer = tk.Frame(inner, bg=C["ai_border"], padx=1, pady=1)
        bub_outer.pack(anchor="w")
        bub = tk.Frame(bub_outer, bg=C["ai_bubble"])
        bub.pack()

        self._dot_lbl = tk.Label(bub, text="denkt nach …",
                                  bg=C["ai_bubble"], fg=C["ink_light"],
                                  font=("Georgia", 10, "italic"),
                                  padx=14, pady=10)
        self._dot_lbl.pack()
        self._animate(outer)
        self._scroll_bottom()
        return outer

    _anim_frames = ["denkt nach …", "denkt nach  ·", "denkt nach ··", "denkt nach ···"]
    _anim_idx    = 0

    def _animate(self, widget):
        if not widget.winfo_exists():
            return
        try:
            self._dot_lbl.configure(text=self._anim_frames[self._anim_idx % 4])
            self._anim_idx += 1
            self.after(400, lambda: self._animate(widget))
        except Exception:
            pass

    def _scroll_bottom(self):
        self.after(60, lambda: self.canvas.yview_moveto(1.0))


# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = AIChatApp()
    app.mainloop()