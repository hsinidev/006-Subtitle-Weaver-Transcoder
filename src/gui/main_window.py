"""
Main Workspace Window – OCR Screen Snipping & Text Transcriber Pro.
Cyberpunk Gold & Onyx Matrix theme.
Polls telemetry queue at 30 Hz and orchestrates all sub-panels.
"""

import queue
import threading
import time
import pyperclip
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Optional, Callable
from PIL import Image

from src.config import (
    APP_NAME, APP_VERSION, COLORS, TYPOGRAPHY,
    ENGINE_AUTO, ENGINE_RAPIDOCR, ENGINE_TESSERACT,
    FORMAT_PLAIN, FORMAT_MARKDOWN, FORMAT_TSV, FORMAT_JSON,
    PREPROC_NONE, PREPROC_OTSU, PREPROC_GRAYSCALE, PREPROC_SCALE_2X, PREPROC_NOISE_REDUCE,
    DEFAULT_SETTINGS
)
from src.gui.components import (
    CyberButton, CyberLabel, CyberCard, StatusBadge,
    CodeTextBox, SeparatorLine, HistoryCard
)
from src.history_db import HistoryDB
from src.regex_matcher import RegexMatcher
from src.binary_resolver import BinaryResolver


def _c(k: str) -> str:
    return COLORS[k]


class MainWindow:
    POLL_INTERVAL_MS = 33  # ~30 Hz

    def __init__(self, telemetry_queue: queue.Queue, settings: dict,
                 on_trigger_snip: Optional[Callable] = None):
        self.queue = telemetry_queue
        self.settings = dict(DEFAULT_SETTINGS)
        self.settings.update(settings)
        self.on_trigger_snip = on_trigger_snip
        self.db = HistoryDB()
        self.matcher = RegexMatcher()

        # State
        self._current_record_id: Optional[int] = None
        self._last_ocr_image: Optional[Image.Image] = None
        self._history_widgets = []
        self._selected_history_card: Optional[HistoryCard] = None

        self._build_app()

    # ─────────────────────────────────────────────
    #  App Bootstrap
    # ─────────────────────────────────────────────
    def _build_app(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title(f"{APP_NAME}  v{APP_VERSION}")
        self.root.geometry("1280x820")
        self.root.minsize(1100, 700)
        self.root.configure(fg_color=_c("background_primary"))

        try:
            from src.config import ASSETS_DIR
            icon_path = str(ASSETS_DIR / "icon.ico")
            self.root.iconbitmap(icon_path)
        except Exception:
            pass

        self._build_header()
        self._build_body()
        self._build_status_bar()

        # Start queue polling
        self.root.after(self.POLL_INTERVAL_MS, self._poll_queue)

    # ─────────────────────────────────────────────
    #  Header Bar
    # ─────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self.root, fg_color=_c("background_secondary"),
                               height=62, corner_radius=0,
                               border_width=1, border_color=_c("border_color"))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Logo / Title
        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            logo_frame,
            text="◈ OCR",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=_c("accent_primary")
        ).pack(side="left")
        ctk.CTkLabel(
            logo_frame,
            text=" Snipping Pro",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="normal"),
            text_color=_c("text_primary")
        ).pack(side="left")
        ctk.CTkLabel(
            logo_frame,
            text=f"  {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_c("text_secondary")
        ).pack(side="left", pady=(4, 0))

        # Action buttons row (right side)
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=20, pady=10)

        self._hotkey_label = ctk.CTkLabel(
            btn_frame,
            text=f"⌨  {self.settings.get('global_hotkey', 'Ctrl+Alt+X')}",
            font=ctk.CTkFont(family="Cascadia Code", size=11),
            text_color=_c("text_secondary")
        )
        self._hotkey_label.pack(side="left", padx=(0, 12))

        CyberButton(
            btn_frame, text="⬡  Snip Screen",
            command=self._trigger_snip,
            variant="primary", width=150, height=36
        ).pack(side="left", padx=4)

        CyberButton(
            btn_frame, text="✕  Clear",
            command=self._clear_output,
            variant="ghost", width=80, height=36
        ).pack(side="left", padx=4)

        # Hotkey status badge
        self._hk_badge = StatusBadge(btn_frame, state="active")
        self._hk_badge.pack(side="left", padx=(12, 0))

    # ─────────────────────────────────────────────
    #  Body – TabView
    # ─────────────────────────────────────────────
    def _build_body(self):
        self._tabs = ctk.CTkTabview(
            self.root,
            fg_color=_c("background_secondary"),
            segmented_button_fg_color=_c("background_primary"),
            segmented_button_selected_color=_c("accent_primary"),
            segmented_button_selected_hover_color=_c("accent_hover"),
            segmented_button_unselected_color=_c("surface_card"),
            segmented_button_unselected_hover_color=_c("border_color"),
            text_color=_c("text_secondary"),
            text_color_disabled=_c("border_color"),
            border_width=1,
            border_color=_c("border_color"),
            corner_radius=8
        )
        self._tabs.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        self._tabs.add("  Capture & Editor  ")
        self._tabs.add("  History Inspector  ")
        self._tabs.add("  Engine & Settings  ")

        self._build_capture_tab(self._tabs.tab("  Capture & Editor  "))
        self._build_history_tab(self._tabs.tab("  History Inspector  "))
        self._build_settings_tab(self._tabs.tab("  Engine & Settings  "))

    # ─────────────────────────────────────────────
    #  Tab 1 – Capture & Editor
    # ─────────────────────────────────────────────
    def _build_capture_tab(self, parent):
        parent.configure(fg_color=_c("background_secondary"))

        # Top control row
        ctrl_row = CyberCard(parent)
        ctrl_row.pack(fill="x", padx=10, pady=(8, 6))

        ctk.CTkLabel(
            ctrl_row, text="Output Format:",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=_c("text_secondary")
        ).pack(side="left", padx=(12, 6), pady=8)

        self._format_var = ctk.StringVar(value=self.settings.get("output_format", FORMAT_PLAIN))
        for fmt in [FORMAT_PLAIN, FORMAT_MARKDOWN, FORMAT_TSV, FORMAT_JSON]:
            ctk.CTkRadioButton(
                ctrl_row, text=fmt, variable=self._format_var, value=fmt,
                command=self._reformat_output,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=_c("text_secondary"),
                fg_color=_c("accent_primary"),
                hover_color=_c("accent_hover")
            ).pack(side="left", padx=6, pady=8)

        # Pre-processing
        ctk.CTkLabel(ctrl_row, text="|", text_color=_c("border_color")).pack(side="left", padx=4)
        ctk.CTkLabel(
            ctrl_row, text="Pre-Process:",
            font=ctk.CTkFont("Segoe UI", 12), text_color=_c("text_secondary")
        ).pack(side="left", padx=(6, 6))
        self._preproc_var = ctk.StringVar(value=self.settings.get("pre_processing", PREPROC_OTSU))
        self._preproc_menu = ctk.CTkOptionMenu(
            ctrl_row, variable=self._preproc_var,
            values=[PREPROC_NONE, PREPROC_OTSU, PREPROC_GRAYSCALE, PREPROC_SCALE_2X, PREPROC_NOISE_REDUCE],
            fg_color=_c("surface_card"), button_color=_c("accent_primary"),
            button_hover_color=_c("accent_hover"), text_color=_c("text_primary"),
            font=ctk.CTkFont("Segoe UI", 11), width=220
        )
        self._preproc_menu.pack(side="left", padx=4)

        # Main paned area
        paned = ctk.CTkFrame(parent, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        paned.grid_columnconfigure(0, weight=3)
        paned.grid_columnconfigure(1, weight=2)
        paned.grid_rowconfigure(0, weight=1)

        # Left: OCR Text Output
        left_card = CyberCard(paned)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_card.grid_rowconfigure(1, weight=1)
        left_card.grid_columnconfigure(0, weight=1)

        # Editor header
        ed_header = ctk.CTkFrame(left_card, fg_color="transparent")
        ed_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        ctk.CTkLabel(
            ed_header, text="OCR Output",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color=_c("text_primary")
        ).pack(side="left")

        self._engine_badge = ctk.CTkLabel(
            ed_header, text="No Capture",
            font=ctk.CTkFont("Cascadia Code", 10),
            text_color=_c("accent_secondary"),
            fg_color=_c("background_primary"),
            corner_radius=6, padx=6, pady=2
        )
        self._engine_badge.pack(side="left", padx=8)

        CyberButton(
            ed_header, text="⎘ Copy", command=self._copy_output,
            variant="primary", width=80, height=28
        ).pack(side="right", padx=2)
        CyberButton(
            ed_header, text="↓ Export", command=self._export_output,
            variant="ghost", width=80, height=28
        ).pack(side="right", padx=2)

        # Code text box
        self._output_textbox = CodeTextBox(left_card, height=0)
        self._output_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 10))
        self._output_textbox.configure(state="normal")
        self._output_textbox.insert("1.0",
            "# Waiting for capture…\n\n"
            "Press  Ctrl+Alt+X  or click  ⬡ Snip Screen  to begin."
        )
        self._output_textbox.configure(state="disabled")

        # Right: Regex Matches Panel
        right_card = CyberCard(paned)
        right_card.grid(row=0, column=1, sticky="nsew")
        right_card.grid_rowconfigure(1, weight=1)
        right_card.grid_columnconfigure(0, weight=1)

        regex_header = ctk.CTkFrame(right_card, fg_color="transparent")
        regex_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        ctk.CTkLabel(
            regex_header, text="Pattern Matches",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color=_c("text_primary")
        ).pack(side="left")

        self._match_count_label = ctk.CTkLabel(
            regex_header, text="0 matches",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=_c("text_secondary")
        )
        self._match_count_label.pack(side="right")

        self._regex_textbox = CodeTextBox(right_card, height=0)
        self._regex_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 10))
        self._regex_textbox.configure(state="normal")
        self._regex_textbox.insert("1.0", "No patterns detected.\n\nPatterns: URLs · IPs · Emails · JSON · Code · UUIDs")
        self._regex_textbox.configure(state="disabled")

        # Store reference to current items for reformatting
        self._current_items = []
        self._current_raw_text = ""
        self._current_engine = ""
        self._current_elapsed = 0.0
        self._current_confidence = 0.0
        self._current_crop: Optional[Image.Image] = None
        self._current_bbox = (0, 0, 0, 0)

    # ─────────────────────────────────────────────
    #  Tab 2 – History Inspector
    # ─────────────────────────────────────────────
    def _build_history_tab(self, parent):
        parent.configure(fg_color=_c("background_secondary"))

        paned = ctk.CTkFrame(parent, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=10, pady=8)
        paned.grid_columnconfigure(0, weight=1)
        paned.grid_columnconfigure(1, weight=2)
        paned.grid_rowconfigure(1, weight=1)

        # Search bar
        search_row = CyberCard(paned)
        search_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        search_row.grid_columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._search_history())

        ctk.CTkEntry(
            search_row, textvariable=self._search_var, placeholder_text="🔍  Search capture history…",
            fg_color=_c("background_primary"), text_color=_c("text_primary"),
            placeholder_text_color=_c("text_secondary"), border_color=_c("border_color"),
            border_width=1, corner_radius=6,
            font=ctk.CTkFont("Segoe UI", 12), height=34
        ).grid(row=0, column=0, padx=(10, 6), pady=8, sticky="ew")

        CyberButton(
            search_row, text="⟳ Refresh",
            command=self._load_history_list,
            variant="ghost", width=100, height=34
        ).grid(row=0, column=1, padx=(0, 6), pady=8)

        CyberButton(
            search_row, text="🗑 Clear All",
            command=self._clear_all_history,
            variant="danger", width=100, height=34
        ).grid(row=0, column=2, padx=(0, 10), pady=8)

        # Left: scrollable history list
        list_card = CyberCard(paned)
        list_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        list_card.grid_rowconfigure(0, weight=1)
        list_card.grid_columnconfigure(0, weight=1)

        self._history_scroll = ctk.CTkScrollableFrame(
            list_card, fg_color=_c("background_secondary"), label_text="",
            scrollbar_button_color=_c("border_color"),
            scrollbar_button_hover_color=_c("accent_primary")
        )
        self._history_scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._history_scroll.grid_columnconfigure(0, weight=1)

        # Right: preview panel
        preview_card = CyberCard(paned)
        preview_card.grid(row=1, column=1, sticky="nsew")
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        prev_header = ctk.CTkFrame(preview_card, fg_color="transparent")
        prev_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        ctk.CTkLabel(
            prev_header, text="Preview",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color=_c("text_primary")
        ).pack(side="left")

        CyberButton(
            prev_header, text="⎘ Copy",
            command=self._copy_history_preview,
            variant="primary", width=80, height=28
        ).pack(side="right", padx=2)

        CyberButton(
            prev_header, text="🗑 Delete",
            command=self._delete_selected_history,
            variant="danger", width=80, height=28
        ).pack(side="right", padx=2)

        self._history_preview = CodeTextBox(preview_card, height=0)
        self._history_preview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 10))
        self._history_preview.configure(state="normal")
        self._history_preview.insert("1.0", "Select a history entry to preview.")
        self._history_preview.configure(state="disabled")

        self._selected_history_id: Optional[int] = None
        self._load_history_list()

    # ─────────────────────────────────────────────
    #  Tab 3 – Engine & Settings
    # ─────────────────────────────────────────────
    def _build_settings_tab(self, parent):
        parent.configure(fg_color=_c("background_secondary"))

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=8)
        scroll.grid_columnconfigure(0, weight=1)

        row = 0

        def _section(title):
            nonlocal row
            ctk.CTkLabel(
                scroll, text=title,
                font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                text_color=_c("accent_primary")
            ).grid(row=row, column=0, sticky="w", pady=(18, 4))
            SeparatorLine(scroll).grid(row=row + 1, column=0, sticky="ew", pady=(0, 8))
            row += 2

        def _setting_row(label, widget_factory, helper=""):
            nonlocal row
            lbl_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            lbl_frame.grid(row=row, column=0, sticky="ew", pady=3)
            lbl_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                lbl_frame, text=label, anchor="w",
                font=ctk.CTkFont("Segoe UI", 12), text_color=_c("text_secondary"),
                width=200
            ).grid(row=0, column=0, sticky="w")

            widget = widget_factory(lbl_frame)
            widget.grid(row=0, column=1, sticky="w", padx=(12, 0))

            if helper:
                ctk.CTkLabel(
                    lbl_frame, text=helper, anchor="w",
                    font=ctk.CTkFont("Segoe UI", 10), text_color=_c("border_color")
                ).grid(row=1, column=0, columnspan=2, sticky="w", padx=(0, 0))
            row += 1

        # ── OCR Engine Settings
        _section("⬡  OCR Engine Configuration")

        self._engine_var = ctk.StringVar(value=self.settings.get("ocr_engine", ENGINE_AUTO))
        _setting_row("Active OCR Engine:", lambda p: ctk.CTkOptionMenu(
            p, variable=self._engine_var,
            values=[ENGINE_AUTO, ENGINE_RAPIDOCR, ENGINE_TESSERACT],
            fg_color=_c("surface_card"), button_color=_c("accent_primary"),
            button_hover_color=_c("accent_hover"), text_color=_c("text_primary"),
            font=ctk.CTkFont("Segoe UI", 11), width=340
        ))

        # Binary resolver status display
        resolver = BinaryResolver(
            self.settings.get("tesseract_cmd", ""),
            self.settings.get("tessdata_dir", "")
        )
        status = resolver.get_status_summary()

        tess_status_text = f"✔ {status['tesseract_path']}" if status["tesseract_available"] else "✕ Not Found"
        tess_color = _c("success_emerald") if status["tesseract_available"] else _c("danger_red")
        rapid_status_text = "✔ Built-in ONNX" if status["rapidocr_available"] else "✕ Not Installed"
        rapid_color = _c("success_emerald") if status["rapidocr_available"] else _c("danger_red")

        _section_card = CyberCard(scroll)
        _section_card.grid(row=row, column=0, sticky="ew", pady=6)
        row += 1

        for label, val, color in [
            ("Tesseract Binary:", tess_status_text, tess_color),
            (f"  Resolution Tier:", f"Tier {status['tesseract_tier']} – {status['tesseract_desc']}", _c("text_secondary")),
            ("RapidOCR ONNX:", rapid_status_text, rapid_color),
        ]:
            r_frame = ctk.CTkFrame(_section_card, fg_color="transparent")
            r_frame.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(r_frame, text=label, text_color=_c("text_secondary"),
                         font=ctk.CTkFont("Segoe UI", 11), width=160, anchor="w").pack(side="left")
            ctk.CTkLabel(r_frame, text=val, text_color=color,
                         font=ctk.CTkFont("Cascadia Code", 10), anchor="w").pack(side="left")

        # Custom Tesseract binary path
        _section("⚙  Tesseract Binary Override")

        self._tess_path_var = ctk.StringVar(value=self.settings.get("tesseract_cmd", ""))
        _setting_row("Custom tesseract.exe path:",
                     lambda p: ctk.CTkEntry(p, textvariable=self._tess_path_var,
                                            placeholder_text="Leave blank for auto-detection",
                                            fg_color=_c("background_primary"), text_color=_c("text_primary"),
                                            placeholder_text_color=_c("text_secondary"),
                                            border_color=_c("border_color"), width=380),
                     helper="Example: C:\\Program Files\\Tesseract-OCR\\tesseract.exe")

        CyberButton(
            scroll, text="📂  Browse for tesseract.exe",
            command=self._browse_tesseract,
            variant="ghost", width=260
        ).grid(row=row, column=0, sticky="w", pady=(2, 8))
        row += 1

        # ── Capture Settings
        _section("⌨  Global Hotkey & Capture")

        self._hotkey_var = ctk.StringVar(value=self.settings.get("global_hotkey", "ctrl+alt+x"))
        _setting_row("Global Hotkey Combo:", lambda p: ctk.CTkEntry(
            p, textvariable=self._hotkey_var,
            fg_color=_c("background_primary"), text_color=_c("accent_primary"),
            border_color=_c("border_color"), font=ctk.CTkFont("Cascadia Code", 12), width=160
        ), helper="Restart required to apply new hotkey.")

        self._autocopy_var = ctk.BooleanVar(value=self.settings.get("auto_copy", True))
        _setting_row("Auto-copy to Clipboard:", lambda p: ctk.CTkSwitch(
            p, variable=self._autocopy_var, onvalue=True, offvalue=False,
            progress_color=_c("accent_primary"), button_color=_c("background_secondary"),
            text=""
        ))

        # ── Confidence Threshold
        _section("◆  OCR Confidence Threshold")
        self._conf_var = ctk.DoubleVar(value=self.settings.get("min_confidence", 0.30) * 100)

        conf_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        conf_frame.grid(row=row, column=0, sticky="ew")
        row += 1

        self._conf_label = ctk.CTkLabel(
            conf_frame, text=f"Min confidence: {self._conf_var.get():.0f}%",
            font=ctk.CTkFont("Segoe UI", 12), text_color=_c("text_secondary")
        )
        self._conf_label.pack(side="left", padx=(0, 12))

        ctk.CTkSlider(
            conf_frame, from_=0, to=95, variable=self._conf_var,
            command=self._update_conf_label,
            fg_color=_c("border_color"), progress_color=_c("accent_primary"),
            button_color=_c("accent_primary"), button_hover_color=_c("accent_hover"),
            width=280
        ).pack(side="left")

        # ── Save Settings Button
        CyberButton(
            scroll, text="✔  Apply & Save Settings",
            command=self._apply_settings,
            variant="primary", width=240, height=38
        ).grid(row=row, column=0, sticky="w", pady=20)
        row += 1

    # ─────────────────────────────────────────────
    #  Status Footer
    # ─────────────────────────────────────────────
    def _build_status_bar(self):
        bar = ctk.CTkFrame(self.root, fg_color=_c("background_secondary"), height=30,
                            corner_radius=0, border_width=1, border_color=_c("border_color"))
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._status_engine_lbl = ctk.CTkLabel(
            bar, text="Engine: –",
            font=ctk.CTkFont("Segoe UI", 10), text_color=_c("text_secondary")
        )
        self._status_engine_lbl.pack(side="left", padx=12)

        ctk.CTkLabel(bar, text="|", text_color=_c("border_color")).pack(side="left")

        self._status_latency_lbl = ctk.CTkLabel(
            bar, text="Latency: – ms",
            font=ctk.CTkFont("Cascadia Code", 10), text_color=_c("text_secondary")
        )
        self._status_latency_lbl.pack(side="left", padx=12)

        ctk.CTkLabel(bar, text="|", text_color=_c("border_color")).pack(side="left")

        self._status_words_lbl = ctk.CTkLabel(
            bar, text="Words: –",
            font=ctk.CTkFont("Segoe UI", 10), text_color=_c("text_secondary")
        )
        self._status_words_lbl.pack(side="left", padx=12)

        ctk.CTkLabel(bar, text="|", text_color=_c("border_color")).pack(side="left")

        self._status_clipboard_lbl = ctk.CTkLabel(
            bar, text="Clipboard: Ready",
            font=ctk.CTkFont("Segoe UI", 10), text_color=_c("text_secondary")
        )
        self._status_clipboard_lbl.pack(side="left", padx=12)

        self._status_badge = StatusBadge(bar, state="idle")
        self._status_badge.pack(side="right", padx=12)

        self._db_count_lbl = ctk.CTkLabel(
            bar, text=f"DB: {self.db.get_count()} records",
            font=ctk.CTkFont("Segoe UI", 10), text_color=_c("text_secondary")
        )
        self._db_count_lbl.pack(side="right", padx=12)

    # ─────────────────────────────────────────────
    #  Queue Polling (30 Hz)
    # ─────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                self._handle_message(msg)
        except Exception:
            pass
        self.root.after(self.POLL_INTERVAL_MS, self._poll_queue)

    def _handle_message(self, msg: tuple):
        tag = msg[0]

        if tag == "HOTKEY_TRIGGERED":
            self._hk_badge.set_state("processing")
            self._status_badge.set_state("processing")

        elif tag == "CAPTURE_DONE":
            _, img, bbox = msg
            self._current_crop = img
            self._current_bbox = bbox
            self._status_badge.set_state("processing")
            self._status_engine_lbl.configure(text="Engine: Processing…")

        elif tag == "OCR_RESULT":
            _, result, md_text, tsv_text, json_text = msg
            self._on_ocr_result(result, md_text, tsv_text, json_text)

        elif tag == "CAPTURE_CANCELLED":
            self._hk_badge.set_state("active")
            self._status_badge.set_state("idle")

        elif tag == "STATUS":
            _, msg_text = msg
            self._status_engine_lbl.configure(text=msg_text)

        elif tag == "ERROR":
            _, err = msg
            self._status_badge.set_state("error")
            self._output_textbox.configure(state="normal")
            self._output_textbox.delete("1.0", "end")
            self._output_textbox.insert("1.0", f"[ERROR]\n{err}")
            self._output_textbox.configure(state="disabled")

    def _on_ocr_result(self, result, md_text: str, tsv_text: str, json_text: str):
        # Update state
        self._current_items = result.items
        self._current_raw_text = result.raw_text
        self._current_engine = result.engine_used
        self._current_elapsed = result.elapsed_ms
        self._current_confidence = result.confidence

        # Save to DB
        record_id = self.db.save(
            engine=result.engine_used,
            raw_text=result.raw_text,
            markdown_text=md_text,
            tsv_text=tsv_text,
            json_data=json_text,
            capture_image=self._current_crop,
            bbox=self._current_bbox,
            elapsed_ms=result.elapsed_ms,
            confidence=result.confidence
        )
        self._current_record_id = record_id

        # Update output display
        self._reformat_output()

        # Regex matches
        matches = self.matcher.find_all(result.raw_text)
        self._regex_textbox.configure(state="normal")
        self._regex_textbox.delete("1.0", "end")
        self._regex_textbox.insert("1.0", self.matcher.summary_string(matches))
        self._regex_textbox.configure(state="disabled")
        self._match_count_label.configure(text=f"{len(matches)} matches")

        # Auto-copy
        if self.settings.get("auto_copy", True) and result.raw_text:
            pyperclip.copy(result.raw_text)
            self._status_clipboard_lbl.configure(text="Clipboard: ✔ Copied", text_color=_c("success_emerald"))
            self.root.after(3000, lambda: self._status_clipboard_lbl.configure(
                text="Clipboard: Ready", text_color=_c("text_secondary")))

        # Engine badge
        self._engine_badge.configure(text=result.engine_used)

        # Status bar update
        word_count = len(result.raw_text.split())
        self._status_engine_lbl.configure(text=f"Engine: {result.engine_used}")
        self._status_latency_lbl.configure(text=f"Latency: {result.elapsed_ms:.0f} ms",
                                            text_color=_c("success_emerald") if result.elapsed_ms < 200 else _c("warning_amber"))
        self._status_words_lbl.configure(text=f"Words: {word_count}")
        self._status_badge.set_state("ready")
        self._hk_badge.set_state("active")
        self._db_count_lbl.configure(text=f"DB: {self.db.get_count()} records")

    # ─────────────────────────────────────────────
    #  Output Actions
    # ─────────────────────────────────────────────
    def _reformat_output(self, *_):
        if not self._current_items and not self._current_raw_text:
            return
        fmt = self._format_var.get()
        from src.table_reconstructor import TableReconstructor
        reconstructor = TableReconstructor()

        if fmt == FORMAT_PLAIN:
            display_text = self._current_raw_text
        elif fmt == FORMAT_MARKDOWN:
            display_text = reconstructor.reconstruct(self._current_items, FORMAT_MARKDOWN)
        elif fmt == FORMAT_TSV:
            display_text = reconstructor.reconstruct(self._current_items, FORMAT_TSV)
        elif fmt == FORMAT_JSON:
            display_text = reconstructor.reconstruct(self._current_items, FORMAT_JSON)
        else:
            display_text = self._current_raw_text

        self._output_textbox.configure(state="normal")
        self._output_textbox.delete("1.0", "end")
        self._output_textbox.insert("1.0", display_text or "# No text detected.")
        self._output_textbox.configure(state="disabled")

    def _copy_output(self):
        text = self._output_textbox.get_text()
        if text:
            pyperclip.copy(text)
            self._status_clipboard_lbl.configure(text="Clipboard: ✔ Copied", text_color=_c("success_emerald"))
            self.root.after(2500, lambda: self._status_clipboard_lbl.configure(
                text="Clipboard: Ready", text_color=_c("text_secondary")))

    def _export_output(self):
        fmt = self._format_var.get()
        ext_map = {FORMAT_PLAIN: ".txt", FORMAT_MARKDOWN: ".md", FORMAT_TSV: ".tsv", FORMAT_JSON: ".json"}
        ext = ext_map.get(fmt, ".txt")
        path = filedialog.asksaveasfilename(
            title="Export OCR Output",
            defaultextension=ext,
            filetypes=[(f"{fmt} file", f"*{ext}"), ("All files", "*.*")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._output_textbox.get_text())

    def _clear_output(self):
        self._output_textbox.configure(state="normal")
        self._output_textbox.delete("1.0", "end")
        self._output_textbox.insert("1.0", "# Cleared. Ready for next capture.")
        self._output_textbox.configure(state="disabled")
        self._regex_textbox.configure(state="normal")
        self._regex_textbox.delete("1.0", "end")
        self._regex_textbox.insert("1.0", "No patterns detected.")
        self._regex_textbox.configure(state="disabled")
        self._current_items = []
        self._current_raw_text = ""
        self._status_badge.set_state("idle")

    # ─────────────────────────────────────────────
    #  History Tab Actions
    # ─────────────────────────────────────────────
    def _load_history_list(self):
        # Clear existing widgets
        for w in self._history_widgets:
            w.destroy()
        self._history_widgets.clear()

        records = self.db.get_recent(50)
        if not records:
            lbl = ctk.CTkLabel(self._history_scroll, text="No captures yet.",
                               text_color=_c("text_secondary"))
            lbl.grid(row=0, column=0, pady=20)
            self._history_widgets.append(lbl)
            return

        for idx, rec in enumerate(records):
            card = HistoryCard(
                self._history_scroll, record=rec,
                on_click=self._on_history_select
            )
            card.grid(row=idx, column=0, sticky="ew", pady=3, padx=4)
            self._history_widgets.append(card)

    def _search_history(self):
        q = self._search_var.get().strip()
        for w in self._history_widgets:
            w.destroy()
        self._history_widgets.clear()

        records = self.db.search(q, 50) if q else self.db.get_recent(50)
        for idx, rec in enumerate(records):
            card = HistoryCard(
                self._history_scroll, record=rec,
                on_click=self._on_history_select
            )
            card.grid(row=idx, column=0, sticky="ew", pady=3, padx=4)
            self._history_widgets.append(card)

    def _on_history_select(self, rec: dict):
        self._selected_history_id = rec["id"]
        full = self.db.get_by_id(rec["id"])
        if not full:
            return

        # De-highlight previous
        if self._selected_history_card:
            self._selected_history_card.highlight(False)

        # Find and highlight matching card widget
        for w in self._history_widgets:
            if isinstance(w, HistoryCard) and w.record.get("id") == rec["id"]:
                w.highlight(True)
                self._selected_history_card = w
                break

        self._history_preview.configure(state="normal")
        self._history_preview.delete("1.0", "end")
        text = full.get("raw_text", "")
        self._history_preview.insert("1.0",
            f"[{full.get('timestamp')}]  Engine: {full.get('engine')}\n"
            f"Latency: {full.get('elapsed_ms', 0):.0f}ms  |  "
            f"Confidence: {full.get('confidence', 0) * 100:.0f}%\n"
            f"Region: ({full.get('bbox_x1')},{full.get('bbox_y1')}) → "
            f"({full.get('bbox_x2')},{full.get('bbox_y2')})\n"
            f"{'─' * 40}\n{text}"
        )
        self._history_preview.configure(state="disabled")

    def _copy_history_preview(self):
        text = self._history_preview.get("1.0", "end").rstrip()
        if text and text != "Select a history entry to preview.":
            pyperclip.copy(text)

    def _delete_selected_history(self):
        if self._selected_history_id is None:
            return
        if messagebox.askyesno("Delete Record", "Delete this capture record?"):
            self.db.delete(self._selected_history_id)
            self._selected_history_id = None
            self._selected_history_card = None
            self._history_preview.configure(state="normal")
            self._history_preview.delete("1.0", "end")
            self._history_preview.insert("1.0", "Select a history entry to preview.")
            self._history_preview.configure(state="disabled")
            self._load_history_list()
            self._db_count_lbl.configure(text=f"DB: {self.db.get_count()} records")

    def _clear_all_history(self):
        if messagebox.askyesno("Clear All History", "Permanently delete all capture records?"):
            self.db.clear_all()
            self._load_history_list()
            self._db_count_lbl.configure(text="DB: 0 records")

    # ─────────────────────────────────────────────
    #  Settings Actions
    # ─────────────────────────────────────────────
    def _browse_tesseract(self):
        path = filedialog.askopenfilename(
            title="Select tesseract.exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if path:
            self._tess_path_var.set(path)

    def _update_conf_label(self, val):
        self._conf_label.configure(text=f"Min confidence: {float(val):.0f}%")

    def _apply_settings(self):
        self.settings["ocr_engine"] = self._engine_var.get()
        self.settings["tesseract_cmd"] = self._tess_path_var.get()
        self.settings["global_hotkey"] = self._hotkey_var.get()
        self.settings["auto_copy"] = self._autocopy_var.get()
        self.settings["min_confidence"] = self._conf_var.get() / 100.0
        messagebox.showinfo("Settings Saved",
            "Settings applied.\nRestart to apply hotkey changes.")

    # ─────────────────────────────────────────────
    #  Snip Trigger
    # ─────────────────────────────────────────────
    def _trigger_snip(self):
        if self.on_trigger_snip:
            self.on_trigger_snip()

    # ─────────────────────────────────────────────
    #  Run
    # ─────────────────────────────────────────────
    def run(self):
        self.root.mainloop()
