"""Motores de reconocimiento de placas.

Todos devuelven un objeto ``Recognition`` o ``None``. El backend ``demo`` sirve
para probar cobros y alertas; no pretende reconocer placas reales. Para reconocer
imagenes reales se puede usar OpenCV + Tesseract u OpenALPR.
"""

import logging
import re
from dataclasses import dataclass

import config

log = logging.getLogger("recognizer")


@dataclass(frozen=True)
class Recognition:
    plate: str
    confidence: float


def normalize_plate(value):
    """Normaliza una placa y rechaza texto que no parezca una matricula."""
    plate = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    return plate if 5 <= len(plate) <= 10 else None


class DemoRecognizer:
    """Devuelve una placa fija para probar el sistema sin una camara real."""

    def recognize(self, frame):
        plate = normalize_plate(config.DEMO_PLATE)
        if frame is None or plate is None:
            return None
        return Recognition(plate=plate, confidence=0.99)


class OpenCVRecognizer:
    """Reconocimiento local de placas mediante OpenCV y Tesseract OCR."""

    def __init__(self):
        import os

        import pytesseract

        tesseract_cmd = config.TESSERACT_CMD
        if not tesseract_cmd and os.name == "nt":
            for candidate in (
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ):
                if os.path.exists(candidate):
                    tesseract_cmd = candidate
                    break
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        self._pytesseract = pytesseract

    @staticmethod
    def _plate_regions(frame):
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(filtered, 30, 200)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        height, width = gray.shape
        candidates = []
        for contour in contours:
            perimeter = cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(polygon) != 4:
                continue
            x, y, region_width, region_height = cv2.boundingRect(polygon)
            if region_height == 0 or region_width < 60:
                continue
            aspect_ratio = region_width / float(region_height)
            area_ratio = (region_width * region_height) / float(height * width)
            if not 1.8 <= aspect_ratio <= 6.5 or not 0.001 <= area_ratio <= 0.5:
                continue
            candidates.append(
                (
                    region_width * region_height,
                    gray[y : y + region_height, x : x + region_width],
                )
            )

        return [
            region
            for _, region in sorted(candidates, key=lambda item: item[0], reverse=True)[
                :8
            ]
        ]

    @staticmethod
    def _plates_in_text(text):
        """Extrae placas mexicanas posibles, incluso con guiones o espacios."""
        ignored_words = {"PLACA", "PLACAS", "MEXICO", "MEX", "ESTADO", "CDMX"}
        words = [
            word
            for word in re.findall(r"[A-Z0-9]+", text.upper())
            if word not in ignored_words
        ]
        combinations = set()
        for size in (1, 2, 3):
            for index in range(len(words) - size + 1):
                combinations.add("".join(words[index : index + size]))

        plates = []
        for combination in combinations:
            plate = normalize_plate(combination)
            if (
                plate
                and any(char.isalpha() for char in plate)
                and any(char.isdigit() for char in plate)
            ):
                plates.append(plate)
        return plates

    def _ocr_candidates(self, image, page_segmentation_mode):
        """Agrupa palabras OCR por linea y conserva su confianza."""
        output = self._pytesseract.Output.DICT
        data = self._pytesseract.image_to_data(
            image,
            config=(
                f"--psm {page_segmentation_mode} -c "
                "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
            ),
            output_type=output,
        )

        lines = {}
        for index, raw_text in enumerate(data["text"]):
            text = raw_text.strip()
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                continue
            if not text or confidence < 0:
                continue
            key = (
                data["block_num"][index],
                data["par_num"][index],
                data["line_num"][index],
            )
            lines.setdefault(key, []).append((text, confidence))

        candidates = []
        for words in lines.values():
            text = " ".join(word for word, _ in words)
            confidence = sum(value for _, value in words) / (100.0 * len(words))
            if confidence < config.OCR_MIN_CONFIDENCE:
                continue
            for plate in self._plates_in_text(text):
                candidates.append(Recognition(plate=plate, confidence=confidence))
        return candidates

    def recognize(self, frame):
        if frame is None:
            return None

        import cv2

        try:
            candidates = []
            for region in self._plate_regions(frame):
                enlarged = cv2.resize(
                    region, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC
                )
                _, threshold = cv2.threshold(
                    enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )
                for processed in (enlarged, threshold):
                    candidates.extend(self._ocr_candidates(processed, 7))

            # Si el contorno no fue detectado, intenta texto disperso en la imagen.
            if not candidates:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                candidates.extend(self._ocr_candidates(gray, 11))
        except self._pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError(
                "Tesseract OCR no esta instalado. Instalalo o define TESSERACT_CMD "
                "con la ruta de tesseract.exe."
            ) from exc

        return max(candidates, key=lambda item: item.confidence) if candidates else None


class OpenALPRRecognizer:
    """Cliente para OpenALPR Cloud o un endpoint HTTP local compatible."""

    def __init__(self, cloud):
        self.cloud = cloud
        self.url = config.ALPR_CLOUD_URL if cloud else config.ALPR_DAEMON_URL
        if cloud and not config.ALPR_API_KEY:
            raise ValueError(
                "ALPR_API_KEY es obligatoria para RECOGNITION_BACKEND=openalpr"
            )

    @staticmethod
    def _from_payload(payload):
        candidates = []
        for result in payload.get("results", []):
            plate = normalize_plate(result.get("plate", ""))
            if not plate:
                continue
            confidence = float(result.get("confidence", 0))
            if confidence > 1:
                confidence /= 100.0
            candidates.append(
                Recognition(plate=plate, confidence=max(0.0, min(confidence, 1.0)))
            )
        return max(candidates, key=lambda item: item.confidence) if candidates else None

    def recognize(self, frame):
        if frame is None:
            return None

        import cv2
        import httpx

        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("No se pudo codificar el frame para OpenALPR")

        data = {"country": config.ALPR_DEFAULT_REGION}
        if self.cloud:
            data.update(
                {
                    "secret_key": config.ALPR_API_KEY,
                    "tasks": "plate",
                    "recognize_vehicle": 0,
                }
            )

        response = httpx.post(
            self.url,
            data=data,
            files={"image": ("frame.jpg", encoded.tobytes(), "image/jpeg")},
            timeout=config.ALPR_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return self._from_payload(response.json())


def build_recognizer():
    """Construye el backend indicado por ``RECOGNITION_BACKEND``."""
    backend = config.RECOGNITION_BACKEND
    if backend == "demo":
        return DemoRecognizer()
    if backend == "opencv":
        return OpenCVRecognizer()
    if backend in {"openalpr", "openalpr-api"}:
        return OpenALPRRecognizer(cloud=True)
    if backend in {"windows-local", "local", "alpr-local"}:
        return OpenALPRRecognizer(cloud=False)
    raise ValueError(
        f"Backend de reconocimiento desconocido: {backend}. "
        "Usa demo, opencv, openalpr o windows-local."
    )
