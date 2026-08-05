"""
OCR Screen Snipping & Text Transcriber Pro — Application Entry Point
Bootstraps global hotkey listener, worker thread pool, telemetry queue,
and CustomTkinter main workspace window.
"""

import sys
import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from PIL import Image

# ── Ensure src is on the import path
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from src.config import DEFAULT_SETTINGS, ENGINE_AUTO, PREPROC_OTSU, FORMAT_PLAIN
from src.screen_capture import ScreenCapture
from src.image_processor import ImageProcessor
from src.ocr_engine import OCREngine
from src.table_reconstructor import TableReconstructor


# ── Global inter-thread communication queue
telemetry_queue: queue.Queue = queue.Queue()

# ── Shared settings (mutated by GUI settings panel)
app_settings = dict(DEFAULT_SETTINGS)

# ── Thread pool for OCR & pre-processing work
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="OCRWorker")

# ── Prevent concurrent snips
_snip_lock = threading.Lock()


# ═══════════════════════════════════════════════
#  OCR Worker Pipeline
# ═══════════════════════════════════════════════
def _ocr_worker(crop_image: Image.Image, bbox: tuple):
    """
    Runs in a background thread (ThreadPoolExecutor).
    Pipeline:
        1. Image pre-processing (binarize, scale, denoise)
        2. OCR inference (RapidOCR ONNX → Tesseract fallback)
        3. Table reconstruction (Plain / Markdown / TSV / JSON)
        4. Push 'OCR_RESULT' to telemetry_queue
    """
    try:
        # Step 1 – Pre-processing
        preproc_mode = app_settings.get("pre_processing", PREPROC_OTSU)
        processed_pil, _ = ImageProcessor.apply_pipeline(crop_image, preproc_mode)

        # Step 2 – OCR inference
        ocr = OCREngine(
            engine_mode=app_settings.get("ocr_engine", ENGINE_AUTO),
            tesseract_cmd=app_settings.get("tesseract_cmd", ""),
            tessdata_dir=app_settings.get("tessdata_dir", ""),
            min_confidence=float(app_settings.get("min_confidence", 0.30))
        )
        result = ocr.run(processed_pil)

        # Step 3 – Multi-format reconstruction
        reconstructor = TableReconstructor()
        md_text = reconstructor.reconstruct(result.items, "Markdown Table")
        tsv_text = reconstructor.reconstruct(result.items, "TSV (Excel/Sheets)")
        json_text = reconstructor.reconstruct(result.items, "JSON (Structured)")

        # Step 4 – Push result
        telemetry_queue.put(("OCR_RESULT", result, md_text, tsv_text, json_text))

    except Exception as e:
        telemetry_queue.put(("ERROR", str(e)))


# ═══════════════════════════════════════════════
#  Snip Trigger (called by hotkey OR UI button)
# ═══════════════════════════════════════════════
def _launch_snip_overlay():
    """
    Opens the borderless overlay on a dedicated thread.
    Waits for CAPTURE_DONE message then dispatches OCR pipeline.
    """
    if not _snip_lock.acquire(blocking=False):
        return  # Already snipping

    def _overlay_thread():
        try:
            from src.gui.overlay_window import OverlayWindow
            overlay_queue: queue.Queue = queue.Queue()
            overlay = OverlayWindow(overlay_queue)

            # Signal UI that hotkey was received
            telemetry_queue.put(("HOTKEY_TRIGGERED",))

            # Run overlay (blocks until selection made or Esc)
            overlay.show()

            # Process result from overlay_queue
            try:
                msg = overlay_queue.get_nowait()
            except queue.Empty:
                msg = ("CAPTURE_CANCELLED",)

            if msg[0] == "CAPTURE_DONE":
                _, crop_image, bbox = msg
                telemetry_queue.put(("CAPTURE_DONE", crop_image, bbox))
                telemetry_queue.put(("STATUS", "Engine: Running OCR…"))
                _executor.submit(_ocr_worker, crop_image, bbox)
            else:
                telemetry_queue.put(("CAPTURE_CANCELLED",))
        except Exception as e:
            telemetry_queue.put(("ERROR", f"Overlay error: {e}"))
        finally:
            _snip_lock.release()

    t = threading.Thread(target=_overlay_thread, daemon=True, name="OverlayThread")
    t.start()


# ═══════════════════════════════════════════════
#  Global Hotkey Listener
# ═══════════════════════════════════════════════
def _start_hotkey_listener():
    """
    Registers the global OS hotkey via keyboard library.
    Runs in a daemon thread — fires _launch_snip_overlay on trigger.
    """
    def _listener_thread():
        try:
            import keyboard
            hotkey = app_settings.get("global_hotkey", "ctrl+alt+x")
            keyboard.add_hotkey(hotkey, _launch_snip_overlay, suppress=False)
            keyboard.wait()
        except Exception as e:
            telemetry_queue.put(("ERROR", f"Hotkey listener error: {e}"))

    t = threading.Thread(target=_listener_thread, daemon=True, name="HotkeyListener")
    t.start()


# ═══════════════════════════════════════════════
#  Application Entry Point
# ═══════════════════════════════════════════════
def main():
    # Start global hotkey listener background thread
    _start_hotkey_listener()

    # Import and launch main GUI window (blocks in mainloop)
    from src.gui.main_window import MainWindow

    window = MainWindow(
        telemetry_queue=telemetry_queue,
        settings=app_settings,
        on_trigger_snip=_launch_snip_overlay
    )
    window.run()

    # Graceful shutdown
    _executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
