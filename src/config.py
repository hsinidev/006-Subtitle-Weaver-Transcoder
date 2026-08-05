"""
Configuration module for OCR Screen Snipping & Text Transcriber Pro.
Defines theme color palette, default settings, regex patterns, and paths.
"""

import os
import sys
from pathlib import Path

# Application Metadata
APP_NAME = "OCR Screen Snipping & Text Transcriber Pro"
APP_VERSION = "1.0.0-PROD"
APP_ID = "com.antigravity.ocr.snipping.pro"

# Root Directories
APP_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_ROOT / "assets"
BIN_DIR = APP_ROOT / "bin"
TESSERACT_BIN_DIR = BIN_DIR / "tesseract"
TESSDATA_DIR = BIN_DIR / "tessdata"

# User Data Directory
LOCAL_APPDATA = os.environ.get("LOCALAPPDATA", str(Path.home()))
USER_DATA_DIR = Path(LOCAL_APPDATA) / "OCRSnippingToolPro"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = USER_DATA_DIR / "ocr_history.db"

# Design System & Theme: Cyberpunk Gold & Onyx Matrix
THEME_NAME = "Cyberpunk Gold & Onyx Matrix"

COLORS = {
    "background_primary": "#090A0F",
    "background_secondary": "#12141D",
    "surface_card": "#1A1D2B",
    "accent_primary": "#FFB800",       # Cyber Gold
    "accent_secondary": "#00F0FF",     # Cyan Matrix
    "accent_hover": "#E0A200",
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "danger_red": "#EF4444",
    "warning_amber": "#F59E0B",
    "success_emerald": "#10B981",
    "border_color": "#282D3F",
    "overlay_mask": "#090A0F",
    "selection_border": "#FFB800",
    "selection_fill": "#FFB800"
}

TYPOGRAPHY = {
    "font_family": "Segoe UI",
    "code_font": "Cascadia Code",
    "heading_size": 18,
    "subheading_size": 14,
    "body_size": 12,
    "caption_size": 10
}

# OCR Engines
ENGINE_AUTO = "Auto-Fallback (RapidOCR -> Tesseract)"
ENGINE_RAPIDOCR = "RapidOCR ONNX"
ENGINE_TESSERACT = "Tesseract OCR v5.3+"

# Output Formats
FORMAT_PLAIN = "Plain Text"
FORMAT_MARKDOWN = "Markdown Table"
FORMAT_TSV = "TSV (Excel/Sheets)"
FORMAT_JSON = "JSON (Structured)"

# Pre-processing Operations
PREPROC_NONE = "Original (None)"
PREPROC_OTSU = "Otsu Adaptive Thresholding"
PREPROC_GRAYSCALE = "Grayscale + High Contrast"
PREPROC_SCALE_2X = "2x Upscale + Binarize"
PREPROC_NOISE_REDUCE = "Denoise + Binarize"

# Regex Matcher Patterns
REGEX_PATTERNS = {
    "URLs": r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*\??[\w=&\.%-]*',
    "IP Addresses": r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
    "Email Addresses": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    "JSON Blocks": r'\{(?:[^{}]|(?:\{[^{}]*\}))*\ authorization|\{[\s\S]*?\ authorization|[\{\[\s]*".*?":[\s\S]*?[\}\]]',
    "Code Snippets": r'(?:def\s+\w+\(|function\s+\w+\(|class\s+\w+|import\s+\w+|#include\s+<|SELECT\s+.*?\s+FROM)',
    "Hex Colors": r'#(?:[0-9a-fA-F]{3}){1,2}\b',
    "UUIDs": r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
    "Phone Numbers": r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
}

# Default App Settings
DEFAULT_SETTINGS = {
    "global_hotkey": "Ctrl+Alt+X",
    "ocr_engine": ENGINE_AUTO,
    "pre_processing": PREPROC_OTSU,
    "output_format": FORMAT_PLAIN,
    "auto_copy": True,
    "tesseract_cmd": "",
    "tessdata_dir": "",
    "sound_effects": True,
    "min_confidence": 0.3
}
