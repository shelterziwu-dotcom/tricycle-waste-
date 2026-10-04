"""Photo uploads (collection proof, disposal proof, dumping reports).

Files are stored in backend/uploads and served at /uploads/<name>.
The returned URL is what the app sends as photo_url.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.security import get_current_user

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_BYTES = 8 * 1024 * 1024
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

router = APIRouter(tags=["uploads"])


@router.post("/uploads", status_code=201)
async def upload_photo(file: UploadFile, _=Depends(get_current_user)):
    ext = ALLOWED.get(file.content_type or "")
    if not ext:
        raise HTTPException(415, "Only JPEG, PNG or WebP photos are accepted")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Photo is larger than 8 MB")
    UPLOAD_DIR.mkdir(exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}
