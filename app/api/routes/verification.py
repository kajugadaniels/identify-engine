from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status # type: ignore
from app.core.security import verify_internal_api_key
from app.services.image_processor import validate_and_process_image
from app.services.rekognition import compare_faces, extract_text_from_id, check_face_liveness
from app.services.scorer import calculate_composite_score
from app.schemas.verification import VerificationResponse
import logging

logger = logging.getLogger(__name__)

# APIRouter groups related routes — mounted in main.py under /verify
router = APIRouter(prefix="/verify", tags=["Verification"])


@router.post("", response_model=VerificationResponse)
async def verify_identity(
    # Optional: liveness session ID created by the NestJS gateway.
    # When omitted, the liveness check is bypassed (score = 100).
    liveness_session_id: Optional[str] = Form(None),

    # The ID card image uploaded by the user
    id_image: UploadFile = File(..., description="Government-issued ID card"),

    # The selfie captured during the liveness check
    selfie_image: UploadFile = File(..., description="Live selfie of the user"),

    # Dependency injection — rejects request if API key is wrong or missing
    _: str = Depends(verify_internal_api_key),
):
    """
    Main verification endpoint. Called only by the NestJS gateway.

    Flow:
    1. Read and validate both uploaded images
    2. Get liveness score from the already-completed AWS session
    3. Compare the face on the ID card with the selfie
    4. Extract text (name, DOB) from the ID card
    5. Calculate composite score and return the result
    """

    # ── Step 1: Read file bytes ───────────────────────
    id_bytes = await id_image.read()
    selfie_bytes = await selfie_image.read()

    # ── Step 2: Validate and process images ───────────
    # This resizes, converts format and rejects invalid files
    processed_id = validate_and_process_image(id_bytes, label="ID card")
    processed_selfie = validate_and_process_image(selfie_bytes, label="Selfie")

    # ── Step 3: Get liveness score ────────────────────
    logger.info(f"Fetching liveness result for session: {liveness_session_id}")
    liveness_score = check_face_liveness(liveness_session_id)
    logger.info(f"Liveness score: {liveness_score}")

    # ── Step 4: Compare faces ─────────────────────────
    logger.info("Comparing faces between ID card and selfie")
    face_match_score = compare_faces(processed_id, processed_selfie)
    logger.info(f"Face match score: {face_match_score}")

    # ── Step 5: Extract text from ID ──────────────────
    logger.info("Extracting text from ID card")
    ocr_result = extract_text_from_id(processed_id)

    # ── Step 6: Calculate composite score ─────────────
    result = calculate_composite_score(
        liveness_score=liveness_score,
        face_match_score=face_match_score,
        ocr_passed=ocr_result["ocr_passed"],
        extracted_name=ocr_result["extracted_name"],
        extracted_dob=ocr_result["extracted_dob"],
    )

    logger.info(f"Verification complete — score: {result.composite_score}, passed: {result.passed}")
    return result