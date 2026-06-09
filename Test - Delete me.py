



import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import json
import httpx
from datetime import datetime


class KIChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Chat Studio")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.configure(bg="#1a1b2e")

        # State
        self.api_keys = {"Claude": "", "ChatGPT": ""}
        self.current_model = tk.StringVar(value="Claude")
        self.chat_histories = {"Claude": [], "ChatGPT": []}
        self.is_streaming = False

        # Farben
        self.colors = {
            "bg_dark": "#1a1b2e",
            "bg_medium": "#232442",
            "bg_light": "#2d2f54",
            "bg_input": "#353766",
            "accent_claude": "#d4a574",
            "accent_gpt": "#6bcf8e",
            "text_primary": "#e8e8f0",
            "text_secondary": "#9899b3",
            "text_dim": "#6b6d8a",
            "btn_claude": "#c47a2e",
            "btn_gpt": "#2ea45e",
            "btn_send": "#7c5cbf",
            "btn_text": "#ffffff",
            "user_bubble": "#3a3c6e",
            "ai_bubble": "#2a2c50",
            "danger": "#c0392b",
            "danger_hover": "#e74c3c",
        }

        self.setup_styles()
        self.build_ui()
        self.load_api_keys()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure("TFrame", background=self.colors["bg_dark"])
        self.style.configure(
            "Card.TFrame",
            background=self.colors["bg_medium"],
            relief="flat",
        )
        self.style.configure(
            "TLabel",
            background=self.colors["bg_dark"],
            foreground=self.colors["text_primary"],
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Title.TLabel",
            font=("Segoe UI", 18, "bold"),
            foreground=self.colors["accent_claude"],
            background=self.colors["bg_dark"],
        )
        self.style.configure(
            "Subtitle.TLabel",
            font=("Segoe UI", 9),
            foreground=self.colors["text_secondary"],
            background=self.colors["bg_dark"],
        )
        self.style.configure(
            "CardTitle.TLabel",
            font=("Segoe UI", 11, "bold"),
            foreground=self.colors["text_primary"],
            background=self.colors["bg_medium"],
        )
        self.style.configure(
            "CardSub.TLabel",
            font=("Segoe UI", 9),
            foreground=self.colors["text_secondary"],
            background=self.colors["bg_medium"],
        )
        self.style.configure(
            "Status.TLabel",
            font=("Segoe UI", 9),
            foreground=self.colors["text_dim"],
            background=self.colors["bg_dark"],
        )

    def build_ui(self):
        # Container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.sidebar = tk.Frame(
            self.main_container, bg=self.colors["bg_medium"], width=260
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.build_sidebar()

        # Chat-Bereich
        self.chat_area = ttk.Frame(self.main_container)
        self.chat_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.build_chat_area()

    def build_sidebar(self):
        # Logo / Titel
        header = tk.Frame(self.sidebar, bg=self.colors["bg_medium"])
        header.pack(fill=tk.X, padx=20, pady=(25, 5))

        tk.Label(
            header,
            text="⚡ AI Chat Studio",
            font=("Segoe UI", 16, "bold"),
            fg=self.colors["accent_claude"],
            bg=self.colors["bg_medium"],
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Claude & ChatGPT",
            font=("Segoe UI", 9),
            fg=self.colors["text_secondary"],
            bg=self.colors["bg_medium"],
        ).pack(anchor="w", pady=(2, 0))

        # Trennlinie
        tk.Frame(self.sidebar, bg=self.colors["bg_light"], height=1).pack(
            fill=tk.X, padx=20, pady=15
        )

        # Modell-Auswahl
        tk.Label(
            self.sidebar,
            text="MODELL AUSWÄHLEN",
            font=("Segoe UI", 8, "bold"),
            fg=self.colors["text_dim"],
            bg=self.colors["bg_medium"],
        ).pack(anchor="w", padx=20, pady=(0, 8))

        self.model_buttons_frame = tk.Frame(
            self.sidebar, bg=self.colors["bg_medium"]
        )
        self.model_buttons_frame.pack(fill=tk.X, padx=20)

        self.claude_btn = tk.Button(
            self.model_buttons_frame,
            text="🟠  Claude",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["btn_claude"],
            fg=self.colors["btn_text"],
            activebackground="#a8621f",
            activeforeground=self.colors["btn_text"],
            relief="flat",
            cursor="hand2",
            pady=10,
            command=lambda: self.switch_model("Claude"),
        )
        self.claude_btn.pack(fill=tk.X, pady=(0, 6))

        self.gpt_btn = tk.Button(
            self.model_buttons_frame,
            text="🟢  ChatGPT",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_light"],
            fg=self.colors["btn_text"],
            activebackground=self.colors["btn_gpt"],
            activeforeground=self.colors["btn_text"],
            relief="flat",
            cursor="hand2",
            pady=10,
            command=lambda: self.switch_model("ChatGPT"),
        )
        self.gpt_btn.pack(fill=tk.X)

        # Trennlinie
        tk.Frame(self.sidebar, bg=self.colors["bg_light"], height=1).pack(
            fill=tk.X, padx=20, pady=15
        )

        # API-Key Bereich
        tk.Label(
            self.sidebar,
            text="API SCHLÜSSEL",
            font=("Segoe UI", 8, "bold"),
            fg=self.colors["text_dim"],
            bg=self.colors["bg_medium"],
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Claude API Key
        claude_frame = tk.Frame(self.sidebar, bg=self.colors["bg_medium"])
        claude_frame.pack(fill=tk.X, padx=20, pady=(0, 8))

        tk
