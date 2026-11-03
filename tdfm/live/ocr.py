"""Reconnaissance de texte (OCR) sur une image d'écran.

Deux moteurs :
- Windows : l'OCR intégré à Windows 10/11 (aucune installation, rapide) ;
- Tesseract : pour le développement et les tests hors Windows.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True)
class Word:
    text: str
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


class OcrError(RuntimeError):
    pass


class WindowsOcr:
    name = "OCR Windows"

    def __init__(self, languages=("fr", "fr-FR", "en-US")):
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.media.ocr import OcrEngine
        except ImportError as exc:  # pragma: no cover - Windows seulement
            raise OcrError("OCR Windows indisponible") from exc
        self.engine = None
        for tag in languages:
            lang = Language(tag)
            if OcrEngine.is_language_supported(lang):
                self.engine = OcrEngine.try_create_from_language(lang)
                self.language = tag
                break
        if self.engine is None:
            self.engine = OcrEngine.try_create_from_user_profile_languages()
            self.language = "profil"
        if self.engine is None:
            raise OcrError("Aucune langue OCR installée dans Windows")

    async def _recognize(self, image: Image.Image):  # pragma: no cover - Windows seulement
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.security.cryptography import CryptographicBuffer

        rgba = image.convert("RGBA")
        b, g, r, a = rgba.split()[2], rgba.split()[1], rgba.split()[0], rgba.split()[3]
        bgra = Image.merge("RGBA", (b, g, r, a)).tobytes()
        buf = CryptographicBuffer.create_from_byte_array(bgra)
        bmp = SoftwareBitmap.create_copy_from_buffer(
            buf, BitmapPixelFormat.BGRA8, rgba.width, rgba.height, BitmapAlphaMode.PREMULTIPLIED)
        return await self.engine.recognize_async(bmp)

    def read(self, image: Image.Image, scale: float = 1.0) -> list[Word]:  # pragma: no cover
        try:
            from winrt.windows.media.ocr import OcrEngine
            max_dim = OcrEngine.max_image_dimension
        except Exception:
            max_dim = 4096
        if max(image.size) * scale > max_dim:
            scale = max_dim / max(image.size)
        if scale != 1.0:
            image = image.resize((int(image.width * scale), int(image.height * scale)), Image.LANCZOS)
        result = asyncio.run(self._recognize(image))
        words = []
        for line in result.lines:
            for w in line.words:
                r = w.bounding_rect
                words.append(Word(w.text, r.x / scale, r.y / scale, r.width / scale, r.height / scale))
        return words


class TesseractOcr:
    name = "Tesseract"

    def __init__(self, lang: str = "fra"):
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
        except Exception as exc:
            raise OcrError("Tesseract indisponible") from exc
        self.pytesseract = pytesseract
        self.lang = lang

    def read(self, image: Image.Image, scale: float = 2.0) -> list[Word]:
        from PIL import ImageOps
        img = image.convert("L")
        if scale != 1.0:
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        # Texte clair sur fond sombre (interface Dofus) : on inverse pour Tesseract.
        img = ImageOps.invert(img)
        d = self.pytesseract.image_to_data(img, lang=self.lang, config="--psm 6",
                                           output_type=self.pytesseract.Output.DICT)
        out = []
        for i, text in enumerate(d["text"]):
            if text.strip():
                out.append(Word(text.strip(), d["left"][i] / scale, d["top"][i] / scale,
                                d["width"][i] / scale, d["height"][i] / scale))
        return out


def get_backend():
    errors = []
    backends = (WindowsOcr, TesseractOcr) if sys.platform == "win32" else (TesseractOcr,)
    for cls in backends:
        try:
            return cls()
        except OcrError as exc:
            errors.append(str(exc))
    raise OcrError(" ; ".join(errors))
