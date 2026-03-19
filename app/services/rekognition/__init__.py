# app/services/rekognition/__init__.py

# Re-export all public functions from the rekognition package.
#
# This means any file that needs rekognition functions imports like this:
#   from app.services.rekognition import check_face_liveness, compare_faces
#
# The internal file structure (client.py, liveness.py etc.) is hidden
# from the rest of the app — only what's exported here is public API.
# If we ever rename an internal file, nothing outside this folder breaks.

from app.services.rekognition.liveness import check_face_liveness
from app.services.rekognition.face_compare import compare_faces
from app.services.rekognition.ocr import extract_text_from_id

__all__ = [
    "check_face_liveness",
    "compare_faces",
    "extract_text_from_id",
]