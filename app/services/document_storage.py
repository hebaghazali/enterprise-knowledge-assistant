import re
import uuid
from pathlib import Path

UPLOAD_DIR = Path("storage/uploads")


def save_upload_file(content: bytes, original_filename: str) -> tuple[Path, int]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-.]", "_", Path(original_filename).name)
    stored_name = f"{uuid.uuid4()}_{safe_name}"
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(content)
    return dest, len(content)
