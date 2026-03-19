from app.core.config import get_settings
from app.schemas.verification import ScoreBreakdown, VerificationResponse


def calculate_composite_score(
    liveness_score: float,
    face_match_score: float,
    ocr_passed: bool,
    extracted_name: str | None,
    extracted_dob: str | None,
) -> VerificationResponse:
    """
    Calculates the final composite accuracy score from all sub-scores.

    Formula:
        composite = (liveness × 0.35) + (face_match × 0.50) + (ocr × 0.15)

    Weights are loaded from .env so they can be tuned without code changes.
    OCR is binary (passed/failed) so we convert it to 100 or 0 before weighting.

    Thresholds are also from .env:
        - liveness must be >= LIVENESS_THRESHOLD
        - face match must be >= FACE_MATCH_THRESHOLD
        - composite must be >= COMPOSITE_PASS_THRESHOLD
        - ALL three must pass for the verification to pass
    """
    settings = get_settings()

    # Convert OCR boolean to a score out of 100
    ocr_score = 100.0 if ocr_passed else 0.0

    # Apply weights from .env
    composite_score = (
        (liveness_score * settings.liveness_weight) +
        (face_match_score * settings.face_match_weight) +
        (ocr_score * settings.ocr_weight)
    )

    # Round to 2 decimal places for clean display
    composite_score = round(composite_score, 2)

    # All three checks must independently pass their own thresholds
    # A high face match can't compensate for a failed liveness check
    liveness_passed = liveness_score >= settings.liveness_threshold
    face_match_passed = face_match_score >= settings.face_match_threshold
    composite_passed = composite_score >= settings.composite_pass_threshold

    # Final pass requires ALL individual checks to pass
    overall_passed = liveness_passed and face_match_passed and composite_passed

    # Build a human-readable message explaining the result
    message = _build_result_message(
        overall_passed,
        liveness_passed,
        face_match_passed,
        ocr_passed,
    )

    return VerificationResponse(
        composite_score=composite_score,
        passed=overall_passed,
        breakdown=ScoreBreakdown(
            liveness_score=round(liveness_score, 2),
            face_match_score=round(face_match_score, 2),
            ocr_passed=ocr_passed,
        ),
        extracted_name=extracted_name,
        extracted_dob=extracted_dob,
        message=message,
    )


def _build_result_message(
    overall_passed: bool,
    liveness_passed: bool,
    face_match_passed: bool,
    ocr_passed: bool,
) -> str:
    """
    Builds a clear message explaining the result.
    If failed, tells the user exactly which check failed.
    """
    if overall_passed:
        return "Identity verified successfully"

    # Collect which specific checks failed
    failed_checks = []
    if not liveness_passed:
        failed_checks.append("liveness check")
    if not face_match_passed:
        failed_checks.append("face match")
    if not ocr_passed:
        failed_checks.append("ID text extraction")

    failed_str = " and ".join(failed_checks)
    return f"Verification failed: {failed_str} did not meet required threshold"