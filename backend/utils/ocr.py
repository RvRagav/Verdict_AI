"""OCR utilities — OpenCV preprocessing + Tesseract.

Pipeline per image:
    1. Deskew via Hough lines
    2. Sauvola binarisation (handles uneven lighting better than Otsu)
    3. Light denoising
    4. DPI normalisation to ~300

Produces:
    {
        "raw_text": str,
        "words": [{"text_content", "x_min", "y_min", "x_max", "y_max",
                   "confidence", "source_engine"}],
        "page_confidence": float,
    }

Word boxes are normalised to [0, 1] so the frontend can overlay them on
any-size rendering of the same page.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Optional

logger = logging.getLogger(__name__)


def preprocess(image_path: str, output_path: Optional[str] = None) -> str:
    """Run the 4-step preprocess; return the path of the processed image.

    If output_path is omitted, writes alongside the input as
    `<stem>_processed.png`.
    """
    try:
        import cv2
        import numpy as np
        from skimage.filters import threshold_sauvola
    except ImportError as exc:
        logger.warning("OpenCV/skimage not installed: %s", exc)
        return image_path

    img = cv2.imread(image_path)
    if img is None:
        return image_path

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Deskew
    angle = _detect_skew(gray)
    if abs(angle) > 0.3:
        h, w = gray.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        gray = cv2.warpAffine(gray, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    # 2. Sauvola binarisation
    try:
        thresh = threshold_sauvola(gray, window_size=25, k=0.2)
        binarised = (gray > thresh).astype("uint8") * 255
    except Exception:
        _, binarised = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3. Light denoising
    denoised = cv2.fastNlMeansDenoising(binarised, None, h=7,
                                         templateWindowSize=7,
                                         searchWindowSize=21)

    # 4. DPI / size normalisation — ensure shorter dim ≥ 1500 px
    h, w = denoised.shape[:2]
    short = min(h, w)
    if short < 1500:
        scale = 1500 / short
        denoised = cv2.resize(denoised, (int(w * scale), int(h * scale)),
                              interpolation=cv2.INTER_CUBIC)

    out = output_path or image_path.rsplit(".", 1)[0] + "_processed.png"
    cv2.imwrite(out, denoised)
    return out


def _detect_skew(gray) -> float:
    import cv2
    import numpy as np
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, math.pi / 180, 100,
                             minLineLength=100, maxLineGap=10)
    if lines is None:
        return 0.0
    angles = []
    for line in lines[:200]:
        x1, y1, x2, y2 = line[0]
        a = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if -45 < a < 45:
            angles.append(a)
    if not angles:
        return 0.0
    return float(np.median(angles))


def ocr_image(image_path: str) -> dict:
    """Run Tesseract on an image. Returns raw_text + word boxes."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {"raw_text": "", "words": [], "page_confidence": 0.0}

    if not os.path.exists(image_path):
        return {"raw_text": "", "words": [], "page_confidence": 0.0}

    try:
        img = Image.open(image_path)
        width, height = img.size
        data = pytesseract.image_to_data(
            img, output_type=pytesseract.Output.DICT,
            config="--psm 6",
        )
        text = pytesseract.image_to_string(img, config="--psm 6")
    except Exception as exc:
        logger.error("Tesseract failed: %s", exc)
        return {"raw_text": "", "words": [], "page_confidence": 0.0}

    words: list[dict] = []
    confidences: list[float] = []
    for i, t in enumerate(data.get("text", [])):
        t = (t or "").strip()
        if not t:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, IndexError):
            conf = 0.0
        if conf <= 0:
            continue
        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])
        words.append({
            "text_content": t,
            "x_min": x / width if width else 0.0,
            "y_min": y / height if height else 0.0,
            "x_max": (x + w) / width if width else 0.0,
            "y_max": (y + h) / height if height else 0.0,
            "confidence": conf / 100.0,
            "source_engine": "tesseract",
        })
        confidences.append(conf / 100.0)

    page_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "raw_text": text or "",
        "words": words,
        "page_confidence": page_conf,
    }
