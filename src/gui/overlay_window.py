"""
Borderless Semi-Transparent Screen Snipping Overlay Window.
Covers the full desktop with an interactive click-and-drag selection rectangle.
Passes the captured region to the worker queue upon release.
"""

import tkinter as tk
import queue
import time
from PIL import Image
from src.config import COLORS
from src.screen_capture import ScreenCapture


class OverlayWindow:
    """
    Fullscreen borderless transparent overlay for screen region selection.
    Uses pure Tkinter Canvas (NOT customtkinter) so it can display
    at full OS transparency and be set always-on-top.
    """

    MASK_COLOR = "#0A0B10"         # Near-black mask tint
    MASK_ALPHA = 0.55              # Overlay mask alpha
    BORDER_COLOR = COLORS["accent_primary"]    # Cyber Gold selection border
    FILL_ALPHA_HEX = "#FFB80030"   # Semi-transparent gold fill (30 = ~19% alpha)

    def __init__(self, telemetry_queue: queue.Queue):
        self.queue = telemetry_queue
        self._origin_x = 0
        self._origin_y = 0
        self._cur_x = 0
        self._cur_y = 0
        self._rect_id = None
        self._mask_ids = []
        self._hud_id = None
        self._full_screenshot: Image.Image = None
        self._monitor_info: dict = {}
        self._root = None

    def show(self):
        """Grab desktop, then display overlay on current thread."""
        # Take screenshot before overlay opens
        self._full_screenshot, self._monitor_info = ScreenCapture.capture_full_desktop()

        # Build overlay Tk window
        self._root = tk.Tk()
        root = self._root
        root.title("")
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", self.MASK_ALPHA)
        root.overrideredirect(True)
        root.configure(bg=self.MASK_COLOR)
        root.config(cursor="crosshair")

        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
        root.geometry(f"{w}x{h}+0+0")

        self._canvas = tk.Canvas(
            root, bg=self.MASK_COLOR,
            highlightthickness=0, cursor="crosshair"
        )
        self._canvas.pack(fill="both", expand=True)

        # Draw instruction HUD
        self._instruction_id = self._canvas.create_text(
            w // 2, 38,
            text="☩  Drag to select a screen region  ·  Esc to cancel",
            fill=COLORS["accent_primary"],
            font=("Segoe UI", 15, "bold"),
            anchor="center"
        )

        # Mouse bindings
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        root.bind("<Escape>", self._on_cancel)

        root.mainloop()

    def _on_press(self, event):
        self._origin_x = event.x
        self._origin_y = event.y
        self._cur_x = event.x
        self._cur_y = event.y
        self._clear_drawing()

    def _on_drag(self, event):
        self._cur_x = event.x
        self._cur_y = event.y
        self._draw_selection()

    def _draw_selection(self):
        self._clear_drawing()
        x1, y1 = self._origin_x, self._origin_y
        x2, y2 = self._cur_x, self._cur_y

        c = self._canvas
        # Dim mask outside selection (4 rectangles)
        W = c.winfo_width()
        H = c.winfo_height()
        self._mask_ids = [
            c.create_rectangle(0, 0, W, min(y1, y2), fill=self.MASK_COLOR, outline=""),
            c.create_rectangle(0, max(y1, y2), W, H, fill=self.MASK_COLOR, outline=""),
            c.create_rectangle(0, min(y1, y2), min(x1, x2), max(y1, y2), fill=self.MASK_COLOR, outline=""),
            c.create_rectangle(max(x1, x2), min(y1, y2), W, max(y1, y2), fill=self.MASK_COLOR, outline=""),
        ]

        # Gold selection border
        self._rect_id = c.create_rectangle(
            x1, y1, x2, y2,
            outline=self.BORDER_COLOR, width=2,
            fill=""
        )

        # Live dimension HUD
        w_px = abs(x2 - x1)
        h_px = abs(y2 - y1)
        hud_x = max(x1, x2) + 8
        hud_y = min(y1, y2) - 14 if min(y1, y2) > 30 else max(y1, y2) + 8

        self._hud_id = c.create_text(
            hud_x, hud_y,
            text=f"  {w_px} × {h_px} px  ",
            fill=COLORS["accent_primary"],
            font=("Cascadia Code", 11, "bold"),
            anchor="nw"
        )

    def _clear_drawing(self):
        c = self._canvas
        for mid in self._mask_ids:
            c.delete(mid)
        self._mask_ids = []
        if self._rect_id:
            c.delete(self._rect_id)
            self._rect_id = None
        if self._hud_id:
            c.delete(self._hud_id)
            self._hud_id = None

    def _on_release(self, event):
        self._cur_x = event.x
        self._cur_y = event.y
        x1 = min(self._origin_x, self._cur_x)
        y1 = min(self._origin_y, self._cur_y)
        x2 = max(self._origin_x, self._cur_x)
        y2 = max(self._origin_y, self._cur_y)

        # Minimum selection guard (10px)
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            self._on_cancel()
            return

        self._root.destroy()

        # Crop and push to queue
        bbox = (x1, y1, x2, y2)
        cropped = ScreenCapture.crop_region(self._full_screenshot, bbox)
        self.queue.put(("CAPTURE_DONE", cropped, bbox))

    def _on_cancel(self, event=None):
        self._root.destroy()
        self.queue.put(("CAPTURE_CANCELLED",))
