"""
Reusable Cyberpunk Gold & Onyx Matrix CustomTkinter Widgets.
Provides styled cards, badge indicators, animated buttons, and code preview boxes.
"""

import customtkinter as ctk
from typing import Optional, Callable
from src.config import COLORS, TYPOGRAPHY


def _c(key: str) -> str:
    return COLORS[key]


class CyberButton(ctk.CTkButton):
    """Gold-accented action button with hover animation."""
    def __init__(self, master, text: str, command: Optional[Callable] = None,
                 variant: str = "primary", **kwargs):
        color_map = {
            "primary": (_c("accent_primary"), _c("accent_hover")),
            "secondary": (_c("background_secondary"), _c("surface_card")),
            "danger": (_c("danger_red"), "#CC3333"),
            "success": (_c("success_emerald"), "#0DA374"),
            "ghost": ("transparent", _c("surface_card")),
        }
        fg, hover = color_map.get(variant, color_map["primary"])
        text_color = _c("background_primary") if variant in ("primary", "success", "danger") else _c("text_primary")

        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=fg,
            hover_color=hover,
            text_color=text_color,
            font=ctk.CTkFont(family=TYPOGRAPHY["font_family"], size=TYPOGRAPHY["body_size"], weight="bold"),
            corner_radius=6,
            border_width=1 if variant == "ghost" else 0,
            border_color=_c("border_color"),
            **kwargs
        )


class CyberLabel(ctk.CTkLabel):
    """Styled label with theme-consistent colors."""
    def __init__(self, master, text: str, variant: str = "body", **kwargs):
        font_map = {
            "heading": (TYPOGRAPHY["heading_size"], "bold"),
            "subheading": (TYPOGRAPHY["subheading_size"], "bold"),
            "body": (TYPOGRAPHY["body_size"], "normal"),
            "caption": (TYPOGRAPHY["caption_size"], "normal"),
            "code": (TYPOGRAPHY["body_size"], "normal"),
            "accent": (TYPOGRAPHY["body_size"], "bold"),
        }
        color_map = {
            "heading": _c("text_primary"),
            "subheading": _c("text_primary"),
            "body": _c("text_secondary"),
            "caption": _c("text_secondary"),
            "code": _c("accent_secondary"),
            "accent": _c("accent_primary"),
        }
        size, weight = font_map.get(variant, (12, "normal"))
        font_family = TYPOGRAPHY["code_font"] if variant == "code" else TYPOGRAPHY["font_family"]

        super().__init__(
            master,
            text=text,
            font=ctk.CTkFont(family=font_family, size=size, weight=weight),
            text_color=color_map.get(variant, _c("text_secondary")),
            **kwargs
        )


class CyberCard(ctk.CTkFrame):
    """Surface card frame with Cyberpunk Gold border accent."""
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=_c("surface_card"),
            border_color=_c("border_color"),
            border_width=1,
            corner_radius=8,
            **kwargs
        )


class StatusBadge(ctk.CTkLabel):
    """Pill-shaped status badge with dynamic color states."""
    STATES = {
        "active": (_c("success_emerald"), "● ACTIVE"),
        "idle": (_c("text_secondary"), "◌ IDLE"),
        "processing": (_c("warning_amber"), "⟳ PROCESSING"),
        "error": (_c("danger_red"), "✕ ERROR"),
        "ready": (_c("accent_primary"), "◆ READY"),
        "copied": (_c("accent_secondary"), "⎘ COPIED"),
    }

    def __init__(self, master, state: str = "idle", **kwargs):
        color, label = self.STATES.get(state, self.STATES["idle"])
        super().__init__(
            master,
            text=label,
            font=ctk.CTkFont(family=TYPOGRAPHY["font_family"], size=TYPOGRAPHY["caption_size"], weight="bold"),
            text_color=color,
            fg_color=_c("background_secondary"),
            corner_radius=10,
            padx=8, pady=2,
            **kwargs
        )
        self._state = state

    def set_state(self, state: str):
        color, label = self.STATES.get(state, self.STATES["idle"])
        self.configure(text=label, text_color=color)
        self._state = state


class CodeTextBox(ctk.CTkTextbox):
    """Monospaced dark code textbox for OCR output display."""
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=_c("background_primary"),
            text_color=_c("text_primary"),
            font=ctk.CTkFont(family=TYPOGRAPHY["code_font"], size=TYPOGRAPHY["body_size"]),
            scrollbar_button_color=_c("border_color"),
            scrollbar_button_hover_color=_c("accent_primary"),
            corner_radius=6,
            border_width=1,
            border_color=_c("border_color"),
            wrap="none",
            **kwargs
        )

    def set_text(self, text: str):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.insert("1.0", text)
        self.configure(state="disabled")

    def get_text(self) -> str:
        return self.get("1.0", "end").rstrip()


class SeparatorLine(ctk.CTkFrame):
    """Thin horizontal separator line."""
    def __init__(self, master, **kwargs):
        super().__init__(master, height=1, fg_color=_c("border_color"),
                         corner_radius=0, **kwargs)


class HistoryCard(ctk.CTkFrame):
    """Single history entry card with timestamp, engine badge, and preview text."""
    def __init__(self, master, record: dict, on_click: Optional[Callable] = None, **kwargs):
        super().__init__(
            master,
            fg_color=_c("surface_card"),
            border_color=_c("border_color"),
            border_width=1,
            corner_radius=6,
            cursor="hand2",
            **kwargs
        )
        self.record = record
        self.on_click = on_click
        self._build(record)
        self.bind("<Button-1>", self._handle_click)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._handle_click)

    def _build(self, rec: dict):
        # Top row: timestamp + engine badge
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 2))

        ts = rec.get("timestamp", "")
        ctk.CTkLabel(
            top_row, text=ts,
            font=ctk.CTkFont(family=TYPOGRAPHY["font_family"], size=TYPOGRAPHY["caption_size"]),
            text_color=_c("text_secondary")
        ).pack(side="left")

        engine_name = rec.get("engine", "Unknown")
        engine_color = _c("accent_primary") if "Rapid" in engine_name else _c("accent_secondary")
        ctk.CTkLabel(
            top_row, text=engine_name,
            font=ctk.CTkFont(family=TYPOGRAPHY["font_family"], size=TYPOGRAPHY["caption_size"], weight="bold"),
            text_color=engine_color
        ).pack(side="right")

        # Preview text
        preview = rec.get("raw_text", "")
        preview = (preview[:100] + "…") if len(preview) > 100 else preview
        ctk.CTkLabel(
            self, text=preview, wraplength=340, justify="left",
            font=ctk.CTkFont(family=TYPOGRAPHY["font_family"], size=TYPOGRAPHY["caption_size"]),
            text_color=_c("text_primary"), anchor="w"
        ).pack(fill="x", padx=10, pady=(2, 4))

        # Latency info
        ms = rec.get("elapsed_ms", 0)
        conf = rec.get("confidence", 0) * 100
        ctk.CTkLabel(
            self, text=f"⏱ {ms:.0f}ms  |  ⬡ {conf:.0f}% confidence",
            font=ctk.CTkFont(family=TYPOGRAPHY["font_family"], size=TYPOGRAPHY["caption_size"]),
            text_color=_c("text_secondary")
        ).pack(anchor="w", padx=10, pady=(0, 6))

    def _handle_click(self, event=None):
        if self.on_click:
            self.on_click(self.record)

    def highlight(self, active: bool = True):
        self.configure(border_color=_c("accent_primary") if active else _c("border_color"),
                       border_width=2 if active else 1)
