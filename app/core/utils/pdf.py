import os
import tempfile
from pathlib import Path

from fastapi import UploadFile


async def save_upload_to_temp(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "upload.pdf").suffix
    fd, path = tempfile.mkstemp(suffix=suffix)
    content = await upload.read()
    os.write(fd, content)
    os.close(fd)
    return path


def remove_temp_file(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
