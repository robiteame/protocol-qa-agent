from uuid import uuid4
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class DocStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Kind(str, Enum):
    HEADING = "heading" #标题
    PARAGRAPH = "paragraph" #普通段落文本
    TABLE = "table" #表格
    SHEET_ROWS = "sheet_rows" #Excel 的行数据，大表按行分组后的每组（带表头）

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


class IRElement:
    def __init__(self, kind: Kind ,level: int ,text: str, meta: dict | None = None):
        self.kind = kind
        self.level = level
        self.text = text
        self.meta = meta or {}
        
class Chunk(BaseModel):
    doc_id: str
    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    section_path: str
    element_kinds: list[str]
    text: str
    token_count: int
    seq: int