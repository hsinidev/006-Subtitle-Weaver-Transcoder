"""
Dual-Engine OCR Worker: RapidOCR ONNX (primary) and Tesseract v5.3+ (fallback).
Returns structured payloads for spatial table reconstruction.
"""

import time
import io
from typing import Optional, List, Tuple, Dict
from PIL import Image
import numpy as np
from src.config import ENGINE_AUTO, ENGINE_RAPIDOCR, ENGINE_TESSERACT


class OCRResult:
    """Structured OCR result payload."""
    def __init__(self, raw_text: str, items: List[Dict], engine_used: str, elapsed_ms: float, confidence: float = 0.0):
        self.raw_text = raw_text
        self.items = items          # List of {"bbox": [...], "text": str, "confidence": float}
        self.engine_used = engine_used
        self.elapsed_ms = elapsed_ms
        self.confidence = confidence

    def __repr__(self):
        return f"<OCRResult engine={self.engine_used} elapsed={self.elapsed_ms:.1f}ms words={len(self.items)}>"


class OCREngine:
    def __init__(self, engine_mode: str = ENGINE_AUTO,
                 tesseract_cmd: str = "",
                 tessdata_dir: str = "",
                 min_confidence: float = 0.30):
        self.engine_mode = engine_mode
        self.tesseract_cmd = tesseract_cmd
        self.tessdata_dir = tessdata_dir
        self.min_confidence = min_confidence
        self._rapid_engine = None

    def _get_rapid_engine(self):
        if self._rapid_engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._rapid_engine = RapidOCR()
        return self._rapid_engine

    def _run_rapidocr(self, pil_img: Image.Image) -> OCRResult:
        """Run RapidOCR ONNX engine. Returns structured OCR result."""
        t0 = time.perf_counter()
        engine = self._get_rapid_engine()
        arr = np.array(pil_img.convert("RGB"))
        results, elapse = engine(arr)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        items = []
        text_lines = []
        total_conf = 0.0

        if results:
            for entry in results:
                # Entry format: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence
                bbox_pts = entry[0]
                text = entry[1]
                conf = float(entry[2]) if len(entry) > 2 else 0.9

                if conf < self.min_confidence:
                    continue

                xs = [p[0] for p in bbox_pts]
                ys = [p[1] for p in bbox_pts]
                x1, y1 = int(min(xs)), int(min(ys))
                x2, y2 = int(max(xs)), int(max(ys))
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                items.append({
                    "bbox": [x1, y1, x2, y2],
                    "cx": cx, "cy": cy,
                    "text": text,
                    "confidence": conf
                })
                text_lines.append(text)
                total_conf += conf

        avg_conf = total_conf / len(items) if items else 0.0
        raw_text = "\n".join(text_lines)
        return OCRResult(raw_text, items, ENGINE_RAPIDOCR, elapsed_ms, avg_conf)

    def _run_tesseract(self, pil_img: Image.Image) -> OCRResult:
        """Run Tesseract OCR v5.3+ engine via pytesseract. Returns structured OCR result."""
        import pytesseract
        from src.binary_resolver import BinaryResolver

        t0 = time.perf_counter()

        # Apply binary resolution
        resolver = BinaryResolver(
            custom_tesseract_path=self.tesseract_cmd,
            custom_tessdata_path=self.tessdata_dir
        )
        bin_path, tier, _ = resolver.resolve_tesseract_binary()
        if bin_path:
            pytesseract.pytesseract.tesseract_cmd = bin_path

        data_path, _, _ = resolver.resolve_tessdata_prefix()
        config = "--oem 3 --psm 11"
        if data_path:
            config = f"--tessdata-dir \"{data_path}\" {config}"

        # image_to_data returns DataFrame-like dict
        tess_data = pytesseract.image_to_data(
            pil_img.convert("RGB"),
            config=config,
            output_type=pytesseract.Output.DICT
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        items = []
        text_lines_raw = []
        total_conf = 0.0

        n = len(tess_data["text"])
        for i in range(n):
            text = tess_data["text"][i].strip()
            conf = int(tess_data["conf"][i])
            if not text or conf < 0:
                continue
            conf_norm = conf / 100.0
            if conf_norm < self.min_confidence:
                continue

            x = int(tess_data["left"][i])
            y = int(tess_data["top"][i])
            w = int(tess_data["width"][i])
            h = int(tess_data["height"][i])
            cx = x + w / 2
            cy = y + h / 2

            items.append({
                "bbox": [x, y, x + w, y + h],
                "cx": cx, "cy": cy,
                "text": text,
                "confidence": conf_norm
            })
            text_lines_raw.append(text)
            total_conf += conf_norm

        avg_conf = total_conf / len(items) if items else 0.0
        raw_text = " ".join(text_lines_raw)
        return OCRResult(raw_text, items, ENGINE_TESSERACT, elapsed_ms, avg_conf)

    def run(self, pil_img: Image.Image) -> OCRResult:
        """Execute OCR using selected engine with Auto-Fallback support."""
        if self.engine_mode == ENGINE_RAPIDOCR:
            try:
                return self._run_rapidocr(pil_img)
            except Exception as e:
                return OCRResult(f"[RapidOCR Error: {e}]", [], ENGINE_RAPIDOCR, 0.0)

        elif self.engine_mode == ENGINE_TESSERACT:
            try:
                return self._run_tesseract(pil_img)
            except Exception as e:
                return OCRResult(f"[Tesseract Error: {e}]", [], ENGINE_TESSERACT, 0.0)

        else:  # ENGINE_AUTO — RapidOCR first, Tesseract fallback
            try:
                result = self._run_rapidocr(pil_img)
                if result.items:
                    return result
                # Fall through to Tesseract if RapidOCR returns nothing
            except Exception:
                pass
            try:
                return self._run_tesseract(pil_img)
            except Exception as e:
                return OCRResult(f"[All OCR Engines Failed: {e}]", [], "None", 0.0)
