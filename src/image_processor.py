"""
On-the-Fly Image Pre-Processing Pipeline using OpenCV and Pillow.
Supports binarization, Otsu adaptive thresholding, contrast enhancement, 
2x Lanczos upscaling, and noise reduction.
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance
from typing import Tuple, Union
from src.config import (
    PREPROC_NONE, PREPROC_OTSU, PREPROC_GRAYSCALE, 
    PREPROC_SCALE_2X, PREPROC_NOISE_REDUCE
)

class ImageProcessor:
    @staticmethod
    def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
        """Converts PIL Image to OpenCV BGR numpy array."""
        rgb_arr = np.array(pil_img.convert('RGB'))
        return cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

    @staticmethod
    def cv2_to_pil(cv2_img: np.ndarray) -> Image.Image:
        """Converts OpenCV BGR or Grayscale numpy array to PIL Image."""
        if len(cv2_img.shape) == 2:
            return Image.fromarray(cv2_img, mode='L')
        rgb_arr = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb_arr)

    @classmethod
    def apply_pipeline(cls, pil_img: Image.Image, mode: str) -> Tuple[Image.Image, np.ndarray]:
        """
        Applies specified pre-processing pipeline to PIL image.
        Returns: (processed_pil_image, processed_cv2_array)
        """
        if pil_img is None:
            raise ValueError("Input image is None")

        # Convert to RGB
        pil_img = pil_img.convert("RGB")

        if mode == PREPROC_NONE:
            cv_img = cls.pil_to_cv2(pil_img)
            return pil_img, cv_img

        elif mode == PREPROC_OTSU:
            cv_img = cls.pil_to_cv2(pil_img)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, binarized = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_pil = cls.cv2_to_pil(binarized)
            return processed_pil, binarized

        elif mode == PREPROC_GRAYSCALE:
            # Grayscale + Contrast Boost
            gray_pil = pil_img.convert("L")
            enhancer = ImageEnhance.Contrast(gray_pil)
            boosted_pil = enhancer.enhance(1.8)
            cv_img = np.array(boosted_pil)
            return boosted_pil, cv_img

        elif mode == PREPROC_SCALE_2X:
            # 2x Lanczos upscaling followed by Otsu thresholding
            w, h = pil_img.size
            scaled_pil = pil_img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
            cv_img = cls.pil_to_cv2(scaled_pil)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, binarized = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_pil = cls.cv2_to_pil(binarized)
            return processed_pil, binarized

        elif mode == PREPROC_NOISE_REDUCE:
            cv_img = cls.pil_to_cv2(pil_img)
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.medianBlur(gray, 3)
            _, binarized = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_pil = cls.cv2_to_pil(binarized)
            return processed_pil, binarized

        else:
            cv_img = cls.pil_to_cv2(pil_img)
            return pil_img, cv_img
