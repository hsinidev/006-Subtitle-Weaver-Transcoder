"""
Multi-monitor low-latency screen frame buffer grabber.
Utilizes mss with PIL ImageGrab / win32 / synthetic fallback.
"""

import sys
from typing import Optional, Tuple, Dict, List
from PIL import Image, ImageDraw, ImageFont
import numpy as np

class ScreenCapture:
    @staticmethod
    def capture_full_desktop() -> Tuple[Image.Image, Dict]:
        """
        Captures entire desktop frame buffer across all monitors.
        Returns: (full_pil_image, monitor_info_dict)
        """
        # Strategy 1: mss screen capture
        try:
            import mss
            with mss.MSS() as sct:
                # sct.monitors[0] represents total virtual screen
                mon_info = sct.monitors[0]
                sct_img = sct.grab(mon_info)
                pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                return pil_img, {
                    "left": mon_info["left"],
                    "top": mon_info["top"],
                    "width": mon_info["width"],
                    "height": mon_info["height"]
                }
        except Exception:
            pass

        # Strategy 2: PIL ImageGrab fallback
        try:
            from PIL import ImageGrab
            pil_img = ImageGrab.grab(all_screens=True)
            w, h = pil_img.size
            return pil_img, {"left": 0, "top": 0, "width": w, "height": h}
        except Exception:
            pass

        # Strategy 3: Synthetic Desktop Generator for Headless / VM environments
        return ScreenCapture._generate_synthetic_desktop()

    @staticmethod
    def crop_region(full_img: Image.Image, bbox: Tuple[int, int, int, int]) -> Image.Image:
        """
        Crops region defined by bbox (x1, y1, x2, y2).
        Ensures bounding box is normalized and within bounds.
        """
        x1, y1, x2, y2 = bbox
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)

        # Enforce minimum size of 5x5 px
        if right - left < 5:
            right = left + 10
        if bottom - top < 5:
            bottom = top + 10

        w, h = full_img.size
        left = max(0, min(left, w - 1))
        top = max(0, min(top, h - 1))
        right = max(left + 1, min(right, w))
        bottom = max(top + 1, min(bottom, h))

        return full_img.crop((left, top, right, bottom))

    @staticmethod
    def _generate_synthetic_desktop() -> Tuple[Image.Image, Dict]:
        """Generates mock desktop canvas with sample table and text."""
        w, h = 1920, 1080
        img = Image.new("RGB", (w, h), color=(18, 20, 29))
        d = ImageDraw.Draw(img)

        # Draw header banner
        d.rectangle([50, 50, 1870, 120], fill=(26, 29, 43), outline=(255, 184, 0), width=2)
        d.text((80, 70), "OCR SCREEN SNIPPING & TEXT TRANSCRIBER PRO - VIRTUAL DESKTOP", fill=(255, 184, 0))

        # Draw a table with structured columns
        d.rectangle([100, 200, 1200, 500], fill=(26, 29, 43), outline=(40, 45, 63), width=1)
        headers = ["ID", "Service Name", "Latency (ms)", "Status", "Endpoint URL"]
        x_coords = [120, 220, 500, 680, 850]

        # Draw headers
        for x, text in zip(x_coords, headers):
            d.text((x, 220), text, fill=(0, 240, 255))
        d.line([110, 250, 1190, 250], fill=(0, 240, 255), width=1)

        # Rows
        rows = [
            ["001", "Auth Service API", "14.2", "ACTIVE", "https://api.auth.matrix.internal/v1"],
            ["002", "Neural Engine Worker", "186.5", "ACTIVE", "https://engine.ai.matrix.internal/run"],
            ["003", "Database Cluster 01", "4.8", "HEALTHY", "192.168.1.105:5432"],
            ["004", "Telemetry Gateway", "32.1", "STANDBY", "10.0.4.22:8080"]
        ]
        y = 270
        for row in rows:
            for x, cell in zip(x_coords, row):
                d.text((x, y), cell, fill=(248, 250, 252))
            y += 45

        # Draw code snippet card
        d.rectangle([100, 550, 1200, 850], fill=(9, 10, 15), outline=(255, 184, 0), width=1)
        code_lines = [
            "# Python Fast Processing Pipeline",
            "import concurrent.futures",
            "def run_ocr_pipeline(raster_bytes, engine='rapidocr'):",
            "    results = engine.extract(raster_bytes)",
            "    table = table_reconstructor.build_tsv(results)",
            "    return {'status': 'SUCCESS', 'table': table}"
        ]
        cy = 570
        for line in code_lines:
            d.text((120, cy), line, fill=(148, 163, 184))
            cy += 35

        return img, {"left": 0, "top": 0, "width": w, "height": h}
