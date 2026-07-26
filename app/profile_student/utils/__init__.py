from typing import Any, Dict, List, Tuple

from .critical_field_validator import CriticalFieldValidator
from .pdf_extractor import extract_pdf_markdown
from .upload_file_info import UploadFileInfo, extract_upload_info, get_source_type
from app.profile_student_attribute.utils import decrypt_if_sensitive


def unflatten_attributes(attributes) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for attr in attributes:
        if getattr(attr, "deleted_at", None) is not None:
            continue
        category = attr.category_name
        keys = attr.key.split(".")
        value = decrypt_if_sensitive(attr.key, attr.value)

        current = result.setdefault(category, {})
        for k in keys[:-1]:
            if not isinstance(current.get(k), dict):
                current[k] = {}
            current = current[k]
        if isinstance(current, dict):
            current[keys[-1]] = value
    return result


def flatten_category(
    category_name: str, fields: Dict[str, Any], prefix: str = ""
) -> List[Tuple[str, str, Any]]:
    items: List[Tuple[str, str, Any]] = []
    for k, v in fields.items():
        key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            items.extend(flatten_category(category_name, v, f"{key}."))
        elif v is not None:
            items.append((category_name, key, v))
    return items


__all__ = [
    "CriticalFieldValidator",
    "UploadFileInfo",
    "extract_pdf_markdown",
    "extract_upload_info",
    "get_source_type",
    "unflatten_attributes",
    "flatten_category",
]
