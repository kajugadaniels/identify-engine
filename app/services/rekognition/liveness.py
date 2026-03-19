import logging
from fastapi import HTTPException, status # type: ignore
from botocore.exceptions import ClientError # type: ignore
from app.services.rekognition.client import get_rekognition_client

logger = logging.getLogger(__name__)


def check_face_liveness(session_id: str) -> float:
    """
    Retrieves the result of a Face Liveness session that was
    already completed on the frontend via AWS Amplify SDK.

    The frontend creates the session and runs the camera challenge.
    This function only reads the result — it does not start a session.

    Args:
        session_id: Session ID returned from the frontend after
                    the liveness check completes

    Returns:
        Confidence score between 0.0 and 100.0
        Higher = more confident the user is a real live person
    """
    client = get_rekognition_client()

    try:
        response = client.get_face_liveness_session_results(
            SessionId=session_id
        )
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