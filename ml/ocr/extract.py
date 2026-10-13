"""Receipt OCR backed by PaddleOCR."""

from pathlib import Path
from typing import Any


class OCRExtractionError(ValueError):
    """Raised when an image cannot be read or OCR cannot extract text."""


def _text_from_result(result: Any) -> list[str]:
    """Extract text from PaddleOCR v2/v3 result shapes."""

    if isinstance(result, dict):
        texts = result.get("rec_texts")
        if isinstance(texts, list):
            return [str(text).strip() for text in texts if str(text).strip()]
        return []
    if isinstance(result, (list, tuple)):
        if (
            len(result) == 2
            and isinstance(result[0], str)
            and isinstance(result[1], (int, float))
        ):
            return [result[0].strip()] if result[0].strip() else []
        texts: list[str] = []
        for item in result:
            texts.extend(_text_from_result(item))
        return texts
    return []


def extract_text(image_path: str | Path) -> str:
    """Extract clean, newline-separated OCR text from an image path."""

    path = Path(image_path)
    if not path.is_file():
        raise OCRExtractionError(f"Image file does not exist: {path}")
    if not path.suffix:
        raise OCRExtractionError(f"Image path has no file extension: {path}")

    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OCRExtractionError(
            "PaddleOCR is required for receipt OCR; install paddleocr and paddlepaddle"
        ) from exc

    try:
        try:
            # PaddleOCR 3.x constructor; disable optional document stages so the
            # receipt path remains focused on text recognition.
            ocr = PaddleOCR(lang="en", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
        except TypeError:
            try:
                ocr = PaddleOCR(lang="en", show_log=False)
            except TypeError:
                ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.predict(str(path)) if hasattr(ocr, "predict") else ocr.ocr(str(path))
    except Exception as exc:
        raise OCRExtractionError(f"OCR failed for image {path}: {exc}") from exc

    text = "\n".join(_text_from_result(result)).strip()
    if not text:
        raise OCRExtractionError(f"OCR returned no text for image: {path}")
    return text
