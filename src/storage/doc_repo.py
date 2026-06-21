from .database import BaseRepository
from ..core.models import DocRecord, DocStatus
from fastapi import UploadFile
from .files import save_upload, compute_hash
from datetime import datetime

class DocRepo(BaseRepository[DocRecord]):
    model_cls = DocRecord
    table = "docs"
    pk = "doc_id"

    async def insert_doc(self, file: UploadFile) -> dict:
        file_hash = (await compute_hash(file))['file_hash']
        if self.get_by_hash(file_hash):
            return {"error": "该文件已存在请勿重复上传!"}

        await file.seek(0)
        file_desc = await save_upload(file, "data")
        doc = DocRecord(
            filename=file.filename,
            file_hash=file_desc["file_hash"],
            file_type=file.content_type,
            status=DocStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )
        self.insert(doc)
        return file_desc
    def get_by_hash(self, file_hash: str) -> DocRecord | None:
        return self.get_one("file_hash = ?", [file_hash])

    async def delete_file(self, file: UploadFile):
        file_hash = (await compute_hash(file))['file_hash']
        doc = self.get_by_hash(file_hash)
        if doc:
            self._conn.execute("DELETE FROM docs WHERE file_hash = ?", [file_hash])
            self._conn.commit()

    def update_status(self, doc_id: str, status: DocStatus,
                      error_msg: str | None = None):
        self._conn.execute(
            "UPDATE docs SET status = ?, error_msg = ? WHERE doc_id = ?",
            (status.value, error_msg, doc_id),
        )
        self._conn.commit()

    def list_by_status(self, status: DocStatus) -> list[DocRecord]:
        return self.list_all(
            where="status = ?", params=[status.value],
            order="created_at DESC",
        )
