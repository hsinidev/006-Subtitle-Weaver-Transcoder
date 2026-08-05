"""
5-Tier Binary Resolver for Tesseract OCR Executable and Tessdata Models.
Follows strict resolution order specified in system architecture.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional, Tuple
from src.config import APP_ROOT, TESSERACT_BIN_DIR, TESSDATA_DIR

class BinaryResolver:
    def __init__(self, custom_tesseract_path: str = "", custom_tessdata_path: str = ""):
        self.custom_tesseract_path = custom_tesseract_path
        self.custom_tessdata_path = custom_tessdata_path

    def resolve_tesseract_binary(self) -> Tuple[Optional[str], int, str]:
        """
        Resolves tesseract.exe path based on 5-Tier resolution order:
        Tier 1: sys._MEIPASS (PyInstaller bundle)
        Tier 2: <App Root>/bin/tesseract/tesseract.exe
        Tier 3: Windows default paths (Program Files / LocalAppData)
        Tier 4: System environment PATH
        Tier 5: User specified custom path
        
        Returns: (binary_path, tier_level, description)
        """
        # Tier 5: Custom User Setting (if valid file path)
        if self.custom_tesseract_path and os.path.isfile(self.custom_tesseract_path):
            return self.custom_tesseract_path, 5, "User Configured Path"

        # Tier 1: PyInstaller Frozen Bundle (_MEIPASS)
        if hasattr(sys, "_MEIPASS"):
            meipass_tess = Path(sys._MEIPASS) / "bin" / "tesseract" / "tesseract.exe"
            if meipass_tess.is_file():
                return str(meipass_tess), 1, "PyInstaller Bundle (sys._MEIPASS)"

        # Tier 2: Application Root / 'bin/tesseract'
        app_tess = TESSERACT_BIN_DIR / "tesseract.exe"
        if app_tess.is_file():
            return str(app_tess), 2, f"App Subfolder ({app_tess})"

        # Tier 3: Local AppData / Program Files default paths
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", "")

        tier3_candidates = [
            Path(program_files) / "Tesseract-OCR" / "tesseract.exe",
            Path(program_files_x86) / "Tesseract-OCR" / "tesseract.exe",
            Path(local_appdata) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            Path(r"C:\Tesseract-OCR\tesseract.exe")
        ]

        for candidate in tier3_candidates:
            if candidate.is_file():
                return str(candidate), 3, f"Standard OS Path ({candidate})"

        # Tier 4: System environment PATH (shutil.which)
        path_binary = shutil.which("tesseract")
        if path_binary and os.path.isfile(path_binary):
            return path_binary, 4, f"System PATH ({path_binary})"

        return None, 0, "Tesseract Executable Not Found"

    def resolve_tessdata_prefix(self) -> Tuple[Optional[str], int, str]:
        """
        Resolves tessdata folder path containing language traineddata files.
        """
        if self.custom_tessdata_path and os.path.isdir(self.custom_tessdata_path):
            return self.custom_tessdata_path, 5, "User Configured Tessdata"

        if hasattr(sys, "_MEIPASS"):
            meipass_tessdata = Path(sys._MEIPASS) / "bin" / "tessdata"
            if meipass_tessdata.is_dir():
                return str(meipass_tessdata), 1, "PyInstaller Bundle Tessdata"

        if TESSDATA_DIR.is_dir():
            return str(TESSDATA_DIR), 2, f"App Subfolder ({TESSDATA_DIR})"

        # Check alongside resolved tesseract binary
        tess_bin, tier, _ = self.resolve_tesseract_binary()
        if tess_bin:
            bin_parent = Path(tess_bin).parent
            tessdata_candidate = bin_parent / "tessdata"
            if tessdata_candidate.is_dir():
                return str(tessdata_candidate), tier, f"Binary Sister Folder ({tessdata_candidate})"

        return None, 0, "Tessdata Directory Not Found"

    def get_status_summary(self) -> dict:
        """Returns resolution status report dictionary."""
        bin_path, tier, desc = self.resolve_tesseract_binary()
        data_path, data_tier, data_desc = self.resolve_tessdata_prefix()
        
        # Check RapidOCR availability
        rapid_available = False
        try:
            from rapidocr_onnxruntime import RapidOCR
            rapid_available = True
        except ImportError:
            rapid_available = False

        return {
            "tesseract_available": bin_path is not None,
            "tesseract_path": bin_path or "Not Found",
            "tesseract_tier": tier,
            "tesseract_desc": desc,
            "tessdata_path": data_path or "Not Found",
            "rapidocr_available": rapid_available,
            "rapidocr_desc": "Built-in ONNX Runtime Engine" if rapid_available else "Not Installed"
        }
