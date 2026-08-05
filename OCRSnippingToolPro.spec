# OCRSnippingToolPro.spec
# PyInstaller single-file bundle specification
# Run: pyinstaller OCRSnippingToolPro.spec

import sys
import os
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/', 'assets'),
        ('bin/tesseract/', 'bin/tesseract'),
        ('bin/tessdata/', 'bin/tessdata'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageGrab',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageEnhance',
        'pytesseract',
        'rapidocr_onnxruntime',
        'rapidocr_onnxruntime.main',
        'mss',
        'keyboard',
        'pyperclip',
        'queue',
        'sqlite3',
        'cv2',
        'numpy',
        'onnxruntime',
        'shapely',
        'pyclipper',
        'concurrent.futures',
        'threading',
        'src.config',
        'src.binary_resolver',
        'src.screen_capture',
        'src.image_processor',
        'src.ocr_engine',
        'src.table_reconstructor',
        'src.regex_matcher',
        'src.history_db',
        'src.gui.components',
        'src.gui.overlay_window',
        'src.gui.main_window',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas', 'torch', 'tensorflow'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OCRSnippingToolPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,        # GUI app – no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version_info=None,
)
