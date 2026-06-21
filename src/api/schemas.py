from fastapi import APIRouter, UploadFile, HTTPException
from ..storage.database import get_db
from ..storage.doc_repo import DocRepo

router = APIRouter()

@router.post("/api/v1/upload")
async def upload(file: UploadFile):
    repo = DocRepo(get_db("data"))
    try:
        file_desc = await repo.insert_doc(file)
    except Exception:
        await repo.delete_file(file)
        raise HTTPException(status_code=500, detail="Failed to save document")
    return file_desc