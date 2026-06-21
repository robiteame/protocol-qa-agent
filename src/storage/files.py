import hashlib
from pathlib import Path
from fastapi import UploadFile


async def save_upload(file: UploadFile, data_dir: str) -> dict:
    # 读取文件内容
    content = await file.read()
    size = len(content)
    file_hash = hashlib.sha256(content).hexdigest()
    store_dir = Path(data_dir) / "raw" / file_hash[:2]
    store_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix
    final_name = f"{file_hash}{suffix}"
    final_path = store_dir / final_name
    final_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入最终位置（已存在则跳过）
    if not final_path.exists():
        final_path.write_bytes(content)

    return {
        "file_hash": file_hash,
        "file_path": str(final_path),
        "file_size": size,
        "filename": file.filename,
        "file_type": suffix.lstrip(".").lower(),
    }

async def compute_hash(file: UploadFile) -> dict:
    sha256 = hashlib.sha256()
    size = 0
    while chunk := await file.read(64 * 1024):
        sha256.update(chunk)
        size += len(chunk)

    file_hash = sha256.hexdigest()
    return {
        "file_hash": file_hash,
        "file_size": size,
    }
