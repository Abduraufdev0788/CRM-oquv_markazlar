import os
import uuid
from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
import aiofiles

from app.models.user import User
from app.core.dependencies import get_current_user

router = APIRouter(tags=["Uploads"])

UPLOAD_DIR = "uploads"

# Uploads papkasini yaratamiz (agar yo'q bo'lsa)
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/upload", summary="Fayl yuklash")
async def upload_file(
    file: UploadFile = File(...),
):
    """
    Kichik hajmli fayllarni yuklash uchun yordamchi API.
    Fayl `uploads/` jildiga saqlanadi va URL manzili qaytariladi.
    """
    if not file:
        raise HTTPException(status_code=400, detail="Fayl topilmadi")

    # Faylga unikal nom beramiz
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    new_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fayl yuklashda xatolik yuz berdi: {str(e)}")

    # URL orqali faylga kirish manzili (StaticFiles orqali xizmat qilinadi)
    file_url = f"/uploads/{new_filename}"
    
    return {"file_url": file_url}
