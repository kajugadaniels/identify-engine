import boto3 # type: ignore
from botocore.exceptions import BotoCoreError, ClientError # type: ignore
from fastapi import HTTPException, status # type: ignore
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)


def _get_rekognition_client():
    """
    Creates a boto3 Rekognition client using credentials from .env.
    Defined as a function (not module-level) so it always uses
    the latest settings — important for testing with mocked configs.
    """
    settings = get_settings()
    return boto3.client(
        "rekognition",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def check_face_liveness(session_id: str) -> float:
    """
    Retrieves the result of a Face Liveness session.

    The session is created on the frontend using AWS Amplify's
    FaceLivenessDetector component — this function just reads the result.

    Args:
        session_id: The session ID created by the frontend

    Returns:
        Liveness confidence score between 0 and 100
    """
    client = _get_rekognition_client()

    try:
        response = client.get_face_liveness_session_results(
            SessionId=session_id
        )
        # Confidence is 0–100 — higher means more confident it's a real person
        return float(response["Confidence"])

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        if error_code == "SessionNotFoundException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Liveness session not found or expired",
            )
        logger.error(f"Rekognition liveness error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve liveness result from AWS",
        )


def compare_faces(id_image_bytes: bytes, selfie_bytes: bytes) -> float:
    """
    Compares the face on the ID card with the live selfie.

    Uses AWS CompareFaces API which returns a similarity score.
    We set SimilarityThreshold=0 to always get a score back,
    then apply our own threshold from .env.

    Args:
        id_image_bytes: Processed JPEG bytes of the ID card
        selfie_bytes: Processed JPEG bytes of the selfie

    Returns:
        Face similarity score between 0 and 100
    """
    client = _get_rekognition_client()

    try:
        response = client.compare_faces(
            SourceImage={"Bytes": id_image_bytes},   # ID card — the reference
            TargetImage={"Bytes": selfie_bytes},      # Selfie — what we compare against
            SimilarityThreshold=0,                    # Return score even if low
            QualityFilter="HIGH",                     # Reject blurry/dark images
        )

        # If no face found in either image, FaceMatches will be empty
        if not response.get("FaceMatches"):
            logger.warning("No face match found between ID and selfie")
            return 0.0

        # Take the highest similarity score if multiple faces detected
        best_match = max(
            response["FaceMatches"],
            key=lambda x: x["Similarity"]
        )
        return float(best_match["Similarity"])

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        # InvalidParameterException usually means no face was detected
        if error_code == "InvalidParameterException":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No face detected in ID card or selfie image",
            )
        logger.error(f"Rekognition compare_faces error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to compare faces via AWS",
        )


def extract_text_from_id(id_image_bytes: bytes) -> dict:
    """
    Uses AWS DetectText to extract readable text from the ID card.
    Attempts to find the name and date of birth fields.

    Args:
        id_image_bytes: Processed JPEG bytes of the ID card

    Returns:
        Dict with ocr_passed, extracted_name, extracted_dob
    """
    client = _get_rekognition_client()

    try:
        response = client.detect_text(
            Image={"Bytes": id_image_bytes}
        )

        # Collect all detected text blocks — filter to LINE type only
        # LINE gives full readable lines, WORD gives individual tokens
        detected_lines = [
            item["DetectedText"]
            for item in response.get("TextDetections", [])
            if item["Type"] == "LINE" and item["Confidence"] > 70
        ]

        if not detected_lines:
            return {"ocr_passed": False, "extracted_name": None, "extracted_dob": None}

        # Basic heuristic extraction — looks for common ID card patterns
        # In production you'd use a more sophisticated parser per ID type
        extracted_name = _extract_name(detected_lines)
        extracted_dob = _extract_dob(detected_lines)

        return {
            "ocr_passed": True,
            "extracted_name": extracted_name,
            "extracted_dob": extracted_dob,
        }

    except ClientError as e:
        logger.error(f"Rekognition detect_text error: {e}")
        # OCR failure is non-fatal — we continue with ocr_passed=False
        return {"ocr_passed": False, "extracted_name": None, "extracted_dob": None}


def _extract_name(lines: list[str]) -> str | None:
    """
    Looks for a name field in the detected text lines.
    Searches for lines that follow 'NAME', 'SURNAME', or 'FULL NAME' labels.
    """
    name_keywords = {"name", "surname", "full name", "nom", "prénom"}

    for i, line in enumerate(lines):
        if line.lower().strip() in name_keywords:
            # The name is usually on the next line after the label
            if i + 1 < len(lines):
                return lines[i + 1].strip()

    return None


def _extract_dob(lines: list[str]) -> str | None:
    """
    Looks for a date of birth in the detected text lines.
    Searches for lines following 'DATE OF BIRTH', 'DOB', 'D.O.B' labels.
    """
    import re

    dob_keywords = {"date of birth", "dob", "d.o.b", "birth date", "né le", "date naissance"}

    # Also try to find any line that looks like a date (DD/MM/YYYY or similar)
    date_pattern = re.compile(r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b')

    for i, line in enumerate(lines):
        if line.lower().strip() in dob_keywords:
            if i + 1 < len(lines):
                return lines[i + 1].strip()

        # Check if this line itself contains a date pattern
        match = date_pattern.search(line)
        if match:
            return match.group()

    return None