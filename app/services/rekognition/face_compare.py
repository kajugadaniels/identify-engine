import logging
from fastapi import HTTPException, status # type: ignore
from botocore.exceptions import ClientError # type: ignore
from app.services.rekognition.client import get_rekognition_client

logger = logging.getLogger(__name__)


def compare_faces(id_image_bytes: bytes, selfie_bytes: bytes) -> float:
    """
    Compares the face on the ID card against the live selfie
    using AWS Rekognition CompareFaces API.

    We set SimilarityThreshold=0 to always receive a score back
    and apply our own threshold in scorer.py — this keeps the
    scoring logic in one place rather than split across services.

    Args:
        id_image_bytes: Processed JPEG bytes of the ID card photo
        selfie_bytes:   Processed JPEG bytes of the live selfie

    Returns:
        Similarity score between 0.0 and 100.0
        0 = completely different people
        100 = very high confidence it is the same person
    """
    client = get_rekognition_client()

    try:
        response = client.compare_faces(
            # Source = reference image (the ID card)
            SourceImage={"Bytes": id_image_bytes},
            # Target = image to compare against (the selfie)
            TargetImage={"Bytes": selfie_bytes},
            # Always get a score back — we apply threshold ourselves
            SimilarityThreshold=0,
            # Reject low quality images early — saves cost and improves accuracy
            QualityFilter="HIGH",
        )

        face_matches = response.get("FaceMatches", [])

        # No match found — faces are too different or no face detected
        if not face_matches:
            logger.warning("No face match found between ID card and selfie")
            return 0.0

        # If multiple faces detected, use the highest scoring match
        best_match = max(face_matches, key=lambda x: x["Similarity"])
        score = float(best_match["Similarity"])

        logger.info(f"Face comparison score: {score:.2f}")
        return score

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        # This means no face was detected in one or both images
        if error_code == "InvalidParameterException":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No face detected in the ID card or selfie. "
                       "Please ensure both images clearly show a face.",
            )

        logger.error(f"Face comparison failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to compare faces via AWS",
        )