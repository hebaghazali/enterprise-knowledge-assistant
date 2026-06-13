import re
import uuid
from pathlib import Path

from app.core.config import get_settings


def save_upload_file(
    content: bytes,
    original_filename: str,
    upload_dir: Path | None = None,
    document_id: uuid.UUID | None = None,
) -> tuple[Path, int]:
    if upload_dir is None:
        upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-.]", "_", Path(original_filename).name)
    prefix = str(document_id) if document_id is not None else str(uuid.uuid4())
    dest = upload_dir / f"{prefix}_{safe_name}"
    dest.write_bytes(content)
    return dest, len(content)
