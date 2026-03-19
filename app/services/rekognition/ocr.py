import re
import logging
from botocore.exceptions import ClientError # type: ignore
from app.services.rekognition.client import get_rekognition_client

logger = logging.getLogger(__name__)

# Minimum confidence % for a detected text line to be considered valid
# Lines below this are likely noise or partially visible text
OCR_CONFIDENCE_THRESHOLD = 70.0


def extract_text_from_id(id_image_bytes: bytes) -> dict:
    """
    Extracts text from an ID card image using AWS Rekognition DetectText.
    Attempts to parse the person's name and date of birth from the result.

    OCR failure is intentionally non-fatal — if text extraction fails,
    we return ocr_passed=False and continue with the other checks.
    A failed OCR lowers the composite score but does not block the result.

    Args:
        id_image_bytes: Processed JPEG bytes of the ID card

    Returns:
        Dict containing:
            ocr_passed (bool)
            extracted_name (str | None)
            extracted_dob (str | None)
    """
    client = get_rekognition_client()

    try:
        response = client.detect_text(
            Image={"Bytes": id_image_bytes}
        )

        # Filter to LINE type only — gives full readable lines
        # WORD gives individual tokens which are harder to parse
        lines = [
            item["DetectedText"]
            for item in response.get("TextDetections", [])
            if item["Type"] == "LINE"
            and item["Confidence"] >= OCR_CONFIDENCE_THRESHOLD
        ]

        if not lines:
            logger.warning("No text detected in ID card image")
            return _empty_ocr_result()

        logger.info(f"Detected {len(lines)} text lines from ID card")

        extracted_name = _extract_name(lines)
        extracted_dob = _extract_dob(lines)

        return {
            "ocr_passed": True,
            "extracted_name": extracted_name,
            "extracted_dob": extracted_dob,
        }

    except ClientError as e:
        # Log but don't raise — OCR is non-fatal
        logger.error(f"OCR text extraction failed: {e}")
        return _empty_ocr_result()


def _empty_ocr_result() -> dict:
    """
    Returns a consistent empty result when OCR fails or finds nothing.
    Centralised here so we don't repeat this dict in multiple places.
    """
    return {
        "ocr_passed": False,
        "extracted_name": None,
        "extracted_dob": None,
    }


def _extract_name(lines: list[str]) -> str | None:
    """
    Searches for a person's name in the detected text lines.

    Strategy:
    - Look for a line that matches a known name label keyword
    - The name is usually on the line immediately after the label
    """
    # Common name field labels across different ID card formats and languages
    name_labels = {
        "name", "full name", "surname", "last name",
        "nom", "prénom", "nombre", "apellido",
    }

    for i, line in enumerate(lines):
        if line.lower().strip() in name_labels:
            # Name is typically on the next line after the label
            if i + 1 < len(lines):
                candidate = lines[i + 1].strip()
                # Basic sanity check — a name should only contain letters and spaces
                if re.match(r"^[A-Za-z\s\-']+$", candidate):
                    return candidate

    return None


def _extract_dob(lines: list[str]) -> str | None:
    """
    Searches for a date of birth in the detected text lines.

    Strategy:
    1. Look for a line matching a known DOB label, return the next line
    2. Fall back to scanning all lines for a date-shaped pattern
    """
    dob_labels = {
        "date of birth", "dob", "d.o.b", "birth date",
        "né le", "date de naissance", "fecha de nacimiento",
    }

    # Matches common date formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    # Also handles 2-digit years: DD/MM/YY
    date_pattern = re.compile(r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b')

    for i, line in enumerate(lines):
        # Strategy 1 — label followed by date on next line
        if line.lower().strip() in dob_labels:
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if date_pattern.search(next_line):
                    return next_line

        # Strategy 2 — date pattern directly on this line
        match = date_pattern.search(line)
        if match:
            return match.group()

    return None