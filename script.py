"""
AI-zu-AI Konversation: Claude ↔ ChatGPT
Benötigt:
  pip install anthropic openai
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import threading
import time
import os
import subprocess
import platform
import queue
import anthropic
from openai import OpenAI  # OpenAI API


# ─────────────────────────────────────────────
# API-Key Dialog beim Start
# ─────────────────────────────────────────────
class ApiKeyDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("API-Keys eingeben")
        self.configure(bg="#0d0d12")
        self.resizable(False, False)
        self.grab_set()  # Modal

        self.anthropic_key = ""
        self.openai_key = ""
        self.confirmed = False

        self._build()
        self.geometry("460x260")
        # Fenster zentrieren
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 230
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 130
        self.geometry(f"+{x}+{y}")

    def _build(self):
        pad = {"padx": 20, "pady": 6}

        tk.Label(self, text="🔑  API-Keys", font=("Segoe UI", 13, "bold"),
                 bg="#0d0d12", fg="#e2e8f0").pack(pady=(18, 4))
        tk.Label(self, text="Die Keys werden nur lokal in diesem Programm verwendet.",
                 font=("Segoe UI", 9), bg="#0d0d12", fg="#64748b").pack()

        # Anthropic
        tk.Label(self, text="Anthropic API-Key (console.anthropic.com):",
                 bg="#0d0d12", fg="#a78bfa", font=("Segoe UI", 10)).pack(anchor="w", **pad)
        self.entry_anthropic = tk.Entry(self, width=52, show="•",
                                        bg="#1e1e2e", fg="#e2e8f0",
                                        insertbackground="#e2e8f0",
                                        relief="flat", font=("Courier New", 10))
        self.entry_anthropic.pack(padx=20)
        # Vorausfüllen falls Umgebungsvariable gesetzt
        if os.environ.get("ANTHROPIC_API_KEY"):
            self.entry_anthropic.insert(0, os.environ["ANTHROPIC_API_KEY"])

        # OpenAI
        tk.Label(self, text="OpenAI API-Key (platform.openai.com/api-keys):",
                 bg="#0d0d12", fg="#34d399", font=("Segoe UI", 10)).pack(anchor="w", **pad)
        self.entry_openai = tk.Entry(self, width=52, show="•",
                                  bg="#1e1e2e", fg="#e2e8f0",
                                  insertbackground="#e2e8f0",
                                  relief="flat", font=("Courier New", 10))
        self.entry_openai.pack(padx=20)
        if os.environ.get("OPENAI_API_KEY"):
            self.entry_openai.insert(0, os.environ["OPENAI_API_KEY"])

        # Buttons
        btn_frame = tk.Frame(self, bg="#0d0d12")
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="Weiter", command=self._confirm,
                  bg="#6366f1", fg="white", font=("Segoe UI", 10),
                  relief="flat", padx=18, pady=6, cursor="hand2").pack(side="left", padx=6)
        tk.Button(btn_frame, text="Abbrechen", command=self.destroy,
                  bg="#475569", fg="white", font=("Segoe UI", 10),
                  relief="flat", padx=18, pady=6, cursor="hand2").pack(side="left", padx=6)

    def _confirm(self):
        a = self.entry_anthropic.get().strip()
        x = self.entry_openai.get().strip()
        if not a or not x:
            messagebox.showerror("Fehler", "Bitte beide Keys eingeben.", parent=self)
            return
        self.anthropic_key = a
        self.openai_key = x
        self.confirmed = True
        self.destroy()

# ─────────────────────────────────────────────
# Konfiguration
# ─────────────────────────────────────────────
CLAUDE_MODEL  = "claude-sonnet-4-5"
GPT_MODEL     = "gpt-4o"
DELAY_SECONDS = 1.5                        # Pause zwischen Nachrichten
MAX_TOKENS    = 500                        # Token-Limit (etwas Puffer)
MAX_CHARS     = 400                        # Zeichenbegrenzung pro Beitrag

# ─────────────────────────────────────────────
# TTS Stimmen (macOS)
# ─────────────────────────────────────────────
# Siri-Stimmen pro Sprache – Fallback-Listen (erste verfügbare wird genutzt)
TTS_VOICE_CANDIDATES = {
    "en": {"claude": ["Stimme 1", "Samantha", "Karen", "Moira", "Fiona"],
           "gpt":    ["Stimme 2", "Daniel",   "Alex",  "Fred",  "Tom"],
           "user":   ["Stimme 1", "Victoria", "Allison", "Ava"]},
    "de": {"claude": ["Stimme 1", "Anna",    "Petra",   "Amelie"],
           "gpt":    ["Stimme 2", "Stimme 1", "Yannick", "Frederik", "Stefan", "Anna"],
           "user":   ["Stimme 1", "Petra",   "Anna"]},
}

def _get_available_voices() -> set:
    """Gibt alle auf diesem System installierten say-Stimmen zurück.
    Jede Zeile hat das Format: Name    Sprache    # Beispielsatz
    Der Name kann Leerzeichen enthalten (z.B. 'Siri-Stimme 1').
    """
    try:
        result = subprocess.run(["say", "-v", "?"],
                                capture_output=True, text=True, timeout=5)
        voices = set()
        import re
        for line in result.stdout.splitlines():
            # Sprach-Code wie "de_DE" oder "en_US" trennt Name vom Rest
            m = re.match(r"^(.+?)\s{2,}[a-z]{2}_[A-Z]{2}", line)
            if m:
                voices.add(m.group(1).strip())
        return voices
    except Exception:
        return set()

_AVAILABLE_VOICES: set = set()  # wird beim ersten _speak-Aufruf befüllt

def _resolve_voice(lang: str, role: str) -> str:
    """Wählt die erste verfügbare Stimme aus der Kandidatenliste."""
    global _AVAILABLE_VOICES
    if not _AVAILABLE_VOICES:
        _AVAILABLE_VOICES = _get_available_voices()
    candidates = TTS_VOICE_CANDIDATES.get(lang, TTS_VOICE_CANDIDATES["de"]).get(role, ["Alex"])
    for v in candidates:
        if v in _AVAILABLE_VOICES:
            return v
    # letzter Fallback: einfach ersten Kandidaten nehmen und hoffen
    return candidates[0]


DEFAULT_TOPIC = (
    "Diskutiert miteinander: Welche KI-Technologie wird die Welt "
    "in den nächsten 10 Jahren am stärksten verändern?"
)


# ─────────────────────────────────────────────
# Farben & Fonts
# ─────────────────────────────────────────────
BG          = "#0d0d12"
PANEL_BG    = "#14141e"
CLAUDE_CLR  = "#a78bfa"   # Violett
GPT_CLR     = "#10b981"   # Grün
USER_CLR    = "#fbbf24"   # Amber
SYS_CLR     = "#94a3b8"   # Slate
TEXT_CLR    = "#e2e8f0"
BTN_STOP    = "#ef4444"
BTN_INT     = "#f59e0b"
BTN_START   = "#6366f1"
BTN_CLEAR   = "#475569"
FONT_MONO   = ("Courier New", 10)
FONT_UI     = ("Segoe UI", 10)
FONT_TITLE  = ("Segoe UI", 13, "bold")


# ─────────────────────────────────────────────
# Haupt-App
# ─────────────────────────────────────────────
class AIConversationApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Claude ↔ ChatGPT · AI Konversation")
        self.root.configure(bg=BG)
        self.root.geometry("900x700")
        self.root.minsize(700, 500)

        self.tts_enabled  = True
        self.tts_language = "de"   # "de" oder "en"
        self.tts_queue    = queue.Queue()
        self.tts_thread   = None
        self.running   = False
        self.paused    = False
        self.stop_flag = threading.Event()
        self.thread    = None

        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.openai_key    = os.environ.get("OPENAI_API_KEY", "")

        # Gesprächsverlauf je KI
        self.claude_history: list[dict] = []
        self.gpt_history:   list[dict] = []

        self._build_ui()
        self._start_tts_worker()

        # Key-Dialog beim Start, wenn Keys fehlen
        if not self.anthropic_key or not self.openai_key:
            self.root.after(200, self._ask_for_keys)

    # ── UI aufbauen ──────────────────────────
    def _build_ui(self):
        # Titelzeile
        header = tk.Frame(self.root, bg=BG, pady=8)
        header.pack(fill="x", padx=16)
        tk.Label(header, text="⚡ AI · AI KONVERSATION",
                 font=FONT_TITLE, bg=BG, fg=TEXT_CLR).pack(side="left")
        tk.Label(header, text="Claude  ↔  ChatGPT",
                 font=("Segoe UI", 10), bg=BG, fg=SYS_CLR).pack(side="left", padx=12)

        # Modus-Auswahl
        mode_frame = tk.Frame(self.root, bg=PANEL_BG, padx=12, pady=6)
        mode_frame.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(mode_frame, text="Modus:", bg=PANEL_BG,
                 fg=SYS_CLR, font=FONT_UI).pack(side="left")
        self.mode_var = tk.StringVar(value="claude_gpt")
        tk.Radiobutton(mode_frame, text="Claude ↔ ChatGPT", variable=self.mode_var,
                       value="claude_gpt", bg=PANEL_BG, fg=GPT_CLR,
                       selectcolor="#1e1e2e", font=FONT_UI,
                       activebackground=PANEL_BG).pack(side="left", padx=8)
        tk.Radiobutton(mode_frame, text="Claude ↔ Claude (kein OpenAI-Key nötig)", variable=self.mode_var,
                       value="claude_claude", bg=PANEL_BG, fg=CLAUDE_CLR,
                       selectcolor="#1e1e2e", font=FONT_UI,
                       activebackground=PANEL_BG).pack(side="left", padx=8)

        # Sprache
        lang_frame = tk.Frame(self.root, bg=PANEL_BG, padx=12, pady=4)
        lang_frame.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(lang_frame, text="Sprache:", bg=PANEL_BG,
                 fg=SYS_CLR, font=FONT_UI).pack(side="left")
        self.lang_var = tk.StringVar(value="de")
        for code, label in [("de", "🇩🇪  Deutsch"), ("en", "🇬🇧  English")]:
            tk.Radiobutton(lang_frame, text=label, variable=self.lang_var,
                           value=code, bg=PANEL_BG, fg=TEXT_CLR,
                           selectcolor="#1e1e2e", font=FONT_UI,
                           activebackground=PANEL_BG,
                           command=self._on_lang_change).pack(side="left", padx=10)

        # Stimmauswahl
        VOICE_OPTIONS = ["Stimme 1", "Stimme 2", "Anna", "Petra", "Viktor",
                         "Yannick", "Markus", "Samantha", "Daniel", "Victoria"]
        voice_frame = tk.Frame(self.root, bg=PANEL_BG, padx=12, pady=4)
        voice_frame.pack(fill="x", padx=16, pady=(0, 2))

        self.voice_claude_var = tk.StringVar(value="Stimme 1")
        self.voice_gpt_var    = tk.StringVar(value="Stimme 2")
        self.voice_user_var   = tk.StringVar(value="Anna")

        for col, (label, var, clr) in enumerate([
            ("🟣 Claude-Stimme:",  self.voice_claude_var, CLAUDE_CLR),
            ("🟢 ChatGPT-Stimme:", self.voice_gpt_var,    GPT_CLR),
            ("🟡 Moderator-Stimme:", self.voice_user_var, USER_CLR),
        ]):
            cell = tk.Frame(voice_frame, bg=PANEL_BG)
            cell.pack(side="left", padx=(0, 20))
            tk.Label(cell, text=label, bg=PANEL_BG, fg=clr,
                     font=FONT_UI).pack(side="left", padx=(0, 4))
            cb = tk.OptionMenu(cell, var, *VOICE_OPTIONS)
            cb.config(bg="#1e1e2e", fg=TEXT_CLR, activebackground="#2d2d3f",
                      activeforeground=TEXT_CLR, highlightthickness=0,
                      relief="flat", font=FONT_UI, width=10)
            cb["menu"].config(bg="#1e1e2e", fg=TEXT_CLR,
                              activebackground="#6366f1", activeforeground="white")
            cb.pack(side="left")

        # Thema-Eingabe
        topic_frame = tk.Frame(self.root, bg=PANEL_BG, padx=12, pady=8)
        topic_frame.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(topic_frame, text="Gesprächsthema:", bg=PANEL_BG,
                 fg=SYS_CLR, font=FONT_UI).pack(side="left")
        self.topic_var = tk.StringVar(value=DEFAULT_TOPIC)
        tk.Entry(topic_frame, textvariable=self.topic_var,
                 bg="#1e1e2e", fg=TEXT_CLR, insertbackground=TEXT_CLR,
                 relief="flat", font=FONT_UI, width=80).pack(side="left", padx=8, fill="x", expand=True)

        # Chat-Bereich
        chat_frame = tk.Frame(self.root, bg=BG)
        chat_frame.pack(fill="both", expand=True, padx=16)

        self.chat = scrolledtext.ScrolledText(
            chat_frame,
            bg=PANEL_BG, fg=TEXT_CLR,
            font=FONT_MONO, wrap=tk.WORD,
            relief="flat", bd=0,
            state="disabled",
            padx=12, pady=10,
        )
        self.chat.pack(fill="both", expand=True)

        # Tag-Farben
        self.chat.tag_config("claude",  foreground=CLAUDE_CLR, font=("Courier New", 10, "bold"))
        self.chat.tag_config("gpt",    foreground=GPT_CLR,   font=("Courier New", 10, "bold"))
        self.chat.tag_config("user",    foreground=USER_CLR,   font=("Courier New", 10, "bold"))
        self.chat.tag_config("system",  foreground=SYS_CLR,    font=("Courier New", 10, "italic"))
        self.chat.tag_config("msg",     foreground=TEXT_CLR)
        self.chat.tag_config("error",   foreground=BTN_STOP)

        # Steuerleiste
        ctrl = tk.Frame(self.root, bg=BG, pady=10)
        ctrl.pack(fill="x", padx=16)

        self.btn_start = tk.Button(ctrl, text="▶  Start", command=self.start_conversation,
                                   bg=BTN_START, fg="black", font=FONT_UI,
                                   relief="flat", padx=14, pady=6, cursor="hand2")
        self.btn_start.pack(side="left", padx=4)

        self.btn_stop = tk.Button(ctrl, text="■  Stop", command=self.stop_conversation,
                                  bg=BTN_STOP, fg="black", font=FONT_UI,
                                  relief="flat", padx=14, pady=6, cursor="hand2",
                                  state="disabled")
        self.btn_stop.pack(side="left", padx=4)

        self.btn_intervene = tk.Button(ctrl, text="✏  Intervenieren", command=self.intervene,
                                       bg=BTN_INT, fg="black", font=FONT_UI,
                                       relief="flat", padx=14, pady=6, cursor="hand2",
                                       state="disabled")
        self.btn_intervene.pack(side="left", padx=4)

        self.btn_clear = tk.Button(ctrl, text="🗑  Leeren", command=self.clear_chat,
                                   bg=BTN_CLEAR, fg="black", font=FONT_UI,
                                   relief="flat", padx=14, pady=6, cursor="hand2")
        self.btn_clear.pack(side="left", padx=4)

        tk.Button(ctrl, text="🔑  Keys", command=self._edit_keys,
                  bg="#cbd5e1", fg="black", font=FONT_UI,
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side="left", padx=4)

        # Rundenzähler
        self.round_var = tk.StringVar(value="Runde: –")
        tk.Label(ctrl, textvariable=self.round_var,
                 bg=BG, fg=SYS_CLR, font=FONT_UI).pack(side="right", padx=8)

        # Status-Leiste
        self.status_var = tk.StringVar(value="Bereit. API-Keys eingeben und Modus waehlen.")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                               bg="#0a0a10", fg=SYS_CLR, font=("Segoe UI", 9),
                               anchor="w", padx=12, pady=4)
        status_bar.pack(fill="x", side="bottom")

    # ── Hilfsmethoden ────────────────────────
    def _append(self, speaker: str, text: str, tag: str = "msg"):
        self.chat.config(state="normal")
        if speaker:
            self.chat.insert("end", f"\n{speaker}\n", tag)
        self.chat.insert("end", text + "\n", "msg")
        self.chat.see("end")
        self.chat.config(state="disabled")

    def _set_status(self, msg: str):
        self.status_var.set(msg)

    def _set_buttons(self, running: bool):
        if running:
            self.btn_start["state"]     = "disabled"
            self.btn_stop["state"]      = "normal"
            self.btn_intervene["state"] = "normal"
        else:
            self.btn_start["state"]     = "normal"
            self.btn_stop["state"]      = "disabled"
            self.btn_intervene["state"] = "disabled"

    # ── Text-to-Speech ───────────────────────
    def _start_tts_worker(self):
        """Hintergrund-Thread der TTS-Jobs sequenziell abarbeitet."""
        def worker():
            while True:
                item = self.tts_queue.get()
                if item is None:
                    break
                text, voice = item
                try:
                    if platform.system() == "Darwin":
                        # macOS: Siri/say
                        subprocess.run(["say", "-v", voice, text],
                                       check=False, timeout=60)
                    elif platform.system() == "Windows":
                        # Windows: PowerShell SAPI
                        ps = (
                            f"Add-Type -AssemblyName System.Speech; "
                            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                            f"$s.Speak([System.Text.Encoding]::UTF8.GetString("
                            f"[System.Text.Encoding]::UTF8.GetBytes('{text}')));"
                        )
                        subprocess.run(["powershell", "-Command", ps],
                                       check=False, timeout=60)
                    else:
                        # Linux: espeak
                        subprocess.run(["espeak", "-v", "de", text],
                                       check=False, timeout=60)
                except Exception:
                    pass
                finally:
                    self.tts_queue.task_done()
        self.tts_thread = threading.Thread(target=worker, daemon=True)
        self.tts_thread.start()

    def _speak(self, text: str, speaker: str = "claude"):
        """Fügt einen TTS-Job in die Warteschlange ein."""
        if not self.tts_enabled:
            return
        if speaker == "claude":
            voice = self.voice_claude_var.get()
        elif speaker in ("gpt", "chatgpt"):
            voice = self.voice_gpt_var.get()
        else:
            voice = self.voice_user_var.get()
        short = text[:400] + ("…" if len(text) > 400 else "")
        self.tts_queue.put((short, voice))

    def _stop_tts(self):
        """Leert die TTS-Warteschlange und stoppt laufende Ausgabe."""
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
                self.tts_queue.task_done()
            except Exception:
                pass
        if platform.system() == "Darwin":
            subprocess.run(["killall", "say"], check=False)
        elif platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "SpeechSynthesizer*"],
                           check=False, stderr=subprocess.DEVNULL)

    def _toggle_tts(self):
        self.tts_enabled = not self.tts_enabled
        if self.tts_enabled:
            self.tts_btn_var.set("🔊  Vorlesen: AN")
            self.btn_tts.config(bg="#0ea5e9")
        else:
            self.tts_btn_var.set("🔇  Vorlesen: AUS")
            self.btn_tts.config(bg="#475569")
            self._stop_tts()

    # ── Key-Dialog ───────────────────────────
    def _ask_for_keys(self):
        dlg = ApiKeyDialog(self.root)
        self.root.wait_window(dlg)
        if dlg.confirmed:
            self.anthropic_key = dlg.anthropic_key
            self.openai_key    = dlg.openai_key
            self._append("── Keys gesetzt ──", "API-Keys wurden erfolgreich gespeichert.", "system")
        else:
            self._append("⚠ Hinweis", "Keine Keys eingegeben. Bitte vor dem Start eingeben.", "error")

    def _edit_keys(self):
        dlg = ApiKeyDialog(self.root)
        self.root.wait_window(dlg)
        if dlg.confirmed:
            self.anthropic_key = dlg.anthropic_key
            self.openai_key    = dlg.openai_key
            self._set_status("API-Keys aktualisiert.")

    # ── API-Clients ──────────────────────────
    def _get_clients(self):
        if not self.anthropic_key:
            raise ValueError("Anthropic API-Key fehlt! Bitte Keys eingeben.")

        claude_client = anthropic.Anthropic(api_key=self.anthropic_key)

        if self.mode_var.get() == "claude_claude":
            # Zweites Claude als Gegenspieler – kein OpenAI-Key noetig
            return claude_client, None
        else:
            if not self.openai_key:
                raise ValueError("OpenAI API-Key fehlt! Hole ihn auf platform.openai.com/api-keys")
            gpt_client = OpenAI(api_key=self.openai_key)
            return claude_client, gpt_client

    def _on_lang_change(self):
        self.tts_language = self.lang_var.get()

    def _system_prompt(self, role: str) -> str:
        """Gibt den System-Prompt in der gewählten Sprache zurück."""
        lang = self.lang_var.get()
        limit = f"Limit your response to a maximum of {MAX_CHARS} characters." if lang == "en" else f"Begrenze deine Antwort auf maximal {MAX_CHARS} Zeichen."
        prompts = {
            "en": {
                "claude":   f"You are having a philosophical conversation with ChatGPT, another AI. Respond precisely in 3-5 sentences and end with a counter-question. {limit}",
                "gpt":      f"You are having a philosophical conversation with Claude, another AI. Respond precisely in 3-5 sentences and end with a counter-question. {limit}",
                "claude_b": f"You are Claude B in a debate with Claude A. Be more critical and contrarian, challenge assumptions. Respond in 3-5 sentences with a counter-question. {limit}",
            },
            "de": {
                "claude":   f"Du führst ein philosophisches Gespräch mit ChatGPT, einer anderen KI. Antworte präzise in 3–5 Sätzen und stelle am Ende eine Gegenfrage. {limit}",
                "gpt":      f"Du führst ein philosophisches Gespräch mit Claude, einer anderen KI. Antworte präzise in 3–5 Sätzen und stelle am Ende eine Gegenfrage. {limit}",
                "claude_b": f"Du bist Claude B im Gespräch mit Claude A. Sei kritischer und hinterfrage Annahmen. Antworte in 3–5 Sätzen mit einer Gegenfrage. {limit}",
            },
        }
        return prompts.get(lang, prompts["de"])[role]

    def _trim(self, text: str) -> str:
        """Kürzt Text auf MAX_CHARS Zeichen, am besten an einem Satzende."""
        if len(text) <= MAX_CHARS:
            return text
        cut = text[:MAX_CHARS]
        # Versuche am letzten Satzende zu kürzen
        for sep in (". ", "! ", "? "):
            idx = cut.rfind(sep)
            if idx > MAX_CHARS // 2:
                return cut[:idx + 1]
        return cut.rstrip() + "…"

    # ── Claude aufrufen ──────────────────────
    def _ask_claude(self, client: anthropic.Anthropic, message: str) -> str:
        self.claude_history.append({"role": "user", "content": message})
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=self._system_prompt("claude"),
            messages=self.claude_history,
        )
        reply = self._trim(response.content[0].text)
        self.claude_history.append({"role": "assistant", "content": reply})
        return reply

    # ── ChatGPT aufrufen ────────────────────
    def _ask_gpt(self, client: OpenAI, message: str) -> str:
        self.gpt_history.append({"role": "user", "content": message})
        response = client.chat.completions.create(
            model=GPT_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": self._system_prompt("gpt")},
                *self.gpt_history,
            ],
        )
        reply = self._trim(response.choices[0].message.content)
        self.gpt_history.append({"role": "assistant", "content": reply})
        return reply

    # ── Claude B (Gegenspieler im Claude↔Claude-Modus) ───
    def _ask_claude_b(self, client: anthropic.Anthropic, message: str) -> str:
        self.gpt_history.append({"role": "user", "content": message})
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=self._system_prompt("claude_b"),
            messages=self.gpt_history,
        )
        reply = self._trim(response.content[0].text)
        self.gpt_history.append({"role": "assistant", "content": reply})
        return reply

    # ── Konversations-Thread ─────────────────
    def _conversation_loop(self):
        try:
            claude_client, gpt_client = self._get_clients()
        except ValueError as e:
            self.root.after(0, lambda: self._append("⚠ Fehler", str(e), "error"))
            self.root.after(0, lambda: self._set_status("Fehler – API-Key fehlt"))
            self.root.after(0, lambda: self._set_buttons(False))
            return

        topic   = self.topic_var.get().strip() or DEFAULT_TOPIC
        current = topic   # erste Nachricht an Claude
        round_n = 0

        self.root.after(0, lambda: self._append(
            "── Gesprächsstart ──",
            f"Thema: {topic}", "system"
        ))

        while not self.stop_flag.is_set():
            round_n += 1
            self.root.after(0, lambda r=round_n: self.round_var.set(f"Runde: {r}"))

            # ── Claude antwortet ──
            self.root.after(0, lambda: self._set_status("Claude denkt …"))
            try:
                claude_reply = self._ask_claude(claude_client, current)
            except Exception as e:
                self.root.after(0, lambda err=e: self._append("⚠ Claude-Fehler", str(err), "error"))
                break

            self.root.after(0, lambda r=claude_reply: self._append(
                "◈ CLAUDE:", r, "claude"
            ))
            self._speak(claude_reply, "claude")

            if self.stop_flag.is_set():
                break

            time.sleep(DELAY_SECONDS)

            # ── ChatGPT / Claude B antwortet ──
            is_cc = self.mode_var.get() == "claude_claude"
            b_name = "CLAUDE B" if is_cc else "CHATGPT"
            b_tag  = "claude" if is_cc else "gpt"
            self.root.after(0, lambda n=b_name: self._set_status(f"{n} denkt …"))
            try:
                if is_cc:
                    gpt_reply = self._ask_claude_b(claude_client, claude_reply)
                else:
                    gpt_reply = self._ask_gpt(gpt_client, claude_reply)
            except Exception as e:
                self.root.after(0, lambda err=e, n=b_name: self._append(f"⚠ {n}-Fehler", str(err), "error"))
                break

            self.root.after(0, lambda r=gpt_reply, n=b_name, t=b_tag: self._append(
                f"◈ {n}:", r, t
            ))
            self._speak(gpt_reply, b_tag)

            current = gpt_reply  # ChatGPT's Antwort -> naechste Eingabe fuer Claude
            time.sleep(DELAY_SECONDS)

        self.root.after(0, lambda: self._append(
            "── Gesprächsende ──", "", "system"
        ))
        self.root.after(0, lambda: self._set_status("Gestoppt."))
        self.root.after(0, lambda: self._set_buttons(False))
        self.running = False

    # ── Button-Aktionen ──────────────────────
    def start_conversation(self):
        if self.running:
            return
        self.running = True
        self.stop_flag.clear()
        self.claude_history.clear()
        self.gpt_history.clear()
        self._set_buttons(True)
        self._set_status("Konversation läuft …")
        self.thread = threading.Thread(target=self._conversation_loop, daemon=True)
        self.thread.start()

    def stop_conversation(self):
        self.stop_flag.set()
        self._stop_tts()
        self._set_status("Wird gestoppt …")

    def intervene(self):
        """Nutzer gibt eine Nachricht ein, die als nächste Eingabe injiziert wird."""
        if not self.running:
            return

        # Kurz pausieren (indem wir den Loop über das Event steuern)
        self.stop_flag.set()
        time.sleep(0.3)

        msg = simpledialog.askstring(
            "Intervenieren",
            "Deine Nachricht an die KIs:",
            parent=self.root
        )

        if msg:
            # Nachricht in beide Historien einfügen
            self.claude_history.append({"role": "user", "content": f"[Menschlicher Moderator]: {msg}"})
            self.gpt_history.append(  {"role": "user", "content": f"[Menschlicher Moderator]: {msg}"})
            self._append("✦ DU (Moderator):", msg, "user")
            self._speak(msg, "user")

            # Konversation mit der User-Nachricht als neuen Startpunkt fortsetzen
            self.stop_flag.clear()
            self.running = True
            self._set_buttons(True)
            self._set_status("Konversation läuft (nach Intervention) …")

            # Neuen Thread, der ab der User-Nachricht weiterläuft
            def _resume():
                try:
                    claude_client, gpt_client = self._get_clients()
                except ValueError as e:
                    self.root.after(0, lambda: self._append("⚠ Fehler", str(e), "error"))
                    return

                current = msg
                while not self.stop_flag.is_set():
                    self.root.after(0, lambda: self._set_status("Claude denkt …"))
                    try:
                        claude_reply = self._ask_claude(claude_client, current)
                    except Exception as e:
                        self.root.after(0, lambda err=e: self._append("⚠ Claude-Fehler", str(err), "error"))
                        break
                    self.root.after(0, lambda r=claude_reply: self._append("◈ CLAUDE:", r, "claude"))
                    if self.stop_flag.is_set():
                        break
                    time.sleep(DELAY_SECONDS)

                    is_cc2 = self.mode_var.get() == "claude_claude"
                    b2_name = "CLAUDE B" if is_cc2 else "CHATGPT"
                    b2_tag  = "claude" if is_cc2 else "gpt"
                    self.root.after(0, lambda n=b2_name: self._set_status(f"{n} denkt …"))
                    try:
                        if is_cc2:
                            gpt_reply = self._ask_claude_b(claude_client, claude_reply)
                        else:
                            gpt_reply = self._ask_gpt(gpt_client, claude_reply)
                    except Exception as e:
                        self.root.after(0, lambda err=e, n=b2_name: self._append(f"⚠ {n}-Fehler", str(err), "error"))
                        break
                    self.root.after(0, lambda r=gpt_reply, n=b2_name, t=b2_tag: self._append(f"◈ {n}:", r, t))
                    current = gpt_reply
                    time.sleep(DELAY_SECONDS)

                self.root.after(0, lambda: self._append("── Gesprächsende ──", "", "system"))
                self.root.after(0, lambda: self._set_status("Gestoppt."))
                self.root.after(0, lambda: self._set_buttons(False))
                self.running = False

            self.thread = threading.Thread(target=_resume, daemon=True)
            self.thread.start()
        else:
            # Fortsetzen ohne Intervention
            self.stop_flag.clear()
            self.running = True
            self._set_buttons(True)
            self._set_status("Konversation fortgesetzt …")
            self.thread = threading.Thread(target=self._conversation_loop, daemon=True)
            self.thread.start()

    def clear_chat(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.config(state="disabled")
        self.round_var.set("Runde: –")
        self._set_status("Chat geleert.")


# ─────────────────────────────────────────────
# Einstiegspunkt
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = AIConversationApp(root)
    root.mainloop()