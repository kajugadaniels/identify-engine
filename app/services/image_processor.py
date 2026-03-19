import io
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException, status # type: ignore


# ── Constants ────────────────────────────────────────────
# Rekognition works best with images in these bounds
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024   # 5MB hard limit
MIN_IMAGE_DIMENSION = 80                 # pixels — too small = no face detected
MAX_IMAGE_DIMENSION = 2048               # pixels — resize if larger to save bandwidth
ALLOWED_FORMATS = {"JPEG", "PNG"}


def validate_and_process_image(file_bytes: bytes, label: str = "image") -> bytes:
    """
    Validates an uploaded image and prepares it for AWS Rekognition.

    Steps:
    1. Check file size
    2. Verify it's a real image (not a renamed .txt file)
    3. Check format is JPEG or PNG
    4. Check minimum dimensions (face must be detectable)
    5. Resize if too large (saves cost + speeds up API call)
    6. Return as JPEG bytes

    Args:
        file_bytes: Raw bytes from the uploaded file
        label: Human-readable name for error messages ("ID card" or "selfie")

    Returns:
        Processed image as JPEG bytes ready for Rekognition
    """

    # ── Step 1: Size check ───────────────────────────
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{label} exceeds maximum size of 5MB",
        )

    # ── Step 2: Verify it's a real image ─────────────
    try:
        image = Image.open(io.BytesIO(file_bytes))
        # .verify() checks the file header — catches fake images
        # We need to re-open after verify because verify() exhausts the stream
        image = Image.open(io.BytesIO(file_bytes))
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} is not a valid image file",
        )

    # ── Step 3: Format check ──────────────────────────
    if image.format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} must be JPEG or PNG, received {image.format}",
        )

    # ── Step 4: Minimum dimension check ──────────────
    width, height = image.size
    if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} is too small ({width}x{height}px). Minimum is {MIN_IMAGE_DIMENSION}x{MIN_IMAGE_DIMENSION}px",
        )

    # ── Step 5: Resize if too large ───────────────────
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        # thumbnail() preserves aspect ratio
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)

    # ── Step 6: Convert to RGB and return as JPEG bytes ──
    # Convert to RGB because PNG can be RGBA — Rekognition prefers RGB JPEG
    image = image.convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()