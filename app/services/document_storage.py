import re
import uuid
from pathlib import Path

from app.core.config import get_settings


def save_upload_file(
    content: bytes,
    original_filename: str,
    upload_dir: Path | None = None,
) -> tuple[Path, int]:
    if upload_dir is None:
        upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-.]", "_", Path(original_filename).name)
    stored_name = f"{uuid.uuid4()}_{safe_name}"
    dest = upload_dir / stored_name
    dest.write_bytes(content)
    return dest, len(content)
