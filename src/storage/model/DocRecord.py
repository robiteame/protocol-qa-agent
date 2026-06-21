from uuid import uuid4
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class DocStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocRecord(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    file_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    file_type: str
    status: DocStatus = DocStatus.PENDING
    error_msg: str | None = None
    chunk_count: int = 0
    embed_model: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
