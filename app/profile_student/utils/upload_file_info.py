from dataclasses import dataclass
from pathlib import Path

from fastapi import File, UploadFile

_SOURCE_TYPE_MAP: dict[str, str] = {
    ".pdf": "pdf",
}


def get_source_type(extension: str) -> str:
    return _SOURCE_TYPE_MAP.get(extension.lower(), "form")


@dataclass
class UploadFileInfo:
    filename: str
    source_type: str
    file: UploadFile


async def extract_upload_info(
    file: UploadFile = File(..., description="CV file in PDF format")
) -> UploadFileInfo:
    filename = file.filename or "unknown"
    extension = Path(filename).suffix
    source_type = get_source_type(extension)
    return UploadFileInfo(filename=filename, source_type=source_type, file=file)
