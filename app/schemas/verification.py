from pydantic import BaseModel, Field
from typing import Optional


class ScoreBreakdown(BaseModel):
    """
    Individual scores from each AWS Rekognition check.
    Returned alongside the final score so the client can
    show a detailed breakdown of why a verification passed or failed.
    """
    liveness_score: float = Field(..., ge=0, le=100, description="AWS Face Liveness score 0–100")
    face_match_score: float = Field(..., ge=0, le=100, description="CompareFaces similarity 0–100")
    ocr_passed: bool = Field(..., description="Whether ID text was successfully extracted")


class VerificationResponse(BaseModel):
    """
    The final response returned to NestJS after a verification attempt.
    NestJS saves this to Postgres and forwards it to the frontend.
    """
    composite_score: float = Field(..., ge=0, le=100, description="Final weighted accuracy score")
    passed: bool = Field(..., description="True if composite_score >= threshold")
    breakdown: ScoreBreakdown
    extracted_name: Optional[str] = Field(None, description="Name read from ID card via OCR")
    extracted_dob: Optional[str] = Field(None, description="Date of birth from ID card")
    message: str = Field(..., description="Human-readable result summary")


class VerificationError(BaseModel):
    """
    Returned when the verification process fails entirely
    (e.g. no face detected, image too blurry).
    """
    success: bool = False
    error: str
    detail: Optional[str] = None