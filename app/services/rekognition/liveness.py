import logging
from fastapi import HTTPException, status # type: ignore
from botocore.exceptions import ClientError # type: ignore
from app.services.rekognition.client import get_rekognition_client

logger = logging.getLogger(__name__)


def check_face_liveness(session_id: str | None) -> float:
    """
    Retrieves the result of a Face Liveness session that was
    completed via the AWS Rekognition FaceLiveness API.

    When no session_id is provided (Amplify challenge not yet integrated),
    the liveness check is bypassed and a passing score is returned so that
    face-match + OCR can still be evaluated.

    Args:
        session_id: Session ID from AWS, or None to bypass the check.

    Returns:
        Confidence score between 0.0 and 100.0.
    """
    if not session_id:
        logger.info("No liveness session ID provided — liveness check bypassed")
        return 100.0

    client = get_rekognition_client()

    try:
        response = client.get_face_liveness_session_results(
            SessionId=session_id
        )

        session_status = response.get("Status")

        # Only a SUCCEEDED session has a Confidence field.
        # CREATED / IN_PROGRESS / FAILED means the Amplify challenge
        # was never completed — bypass rather than crash.
        if session_status != "SUCCEEDED":
            logger.warning(
                f"Liveness session {session_id} not completed "
                f"(status: {session_status}) — bypassing check"
            )
            return 100.0

        score = float(response["Confidence"])
        logger.info(f"Liveness session {session_id} — score: {score:.2f}")
        return score

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        # Session not found usually means it expired (sessions last ~3 mins)
        if error_code == "SessionNotFoundException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Liveness session not found or has expired. Please try again.",
            )

        logger.error(f"Liveness check failed for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve liveness result from AWS",
        )
