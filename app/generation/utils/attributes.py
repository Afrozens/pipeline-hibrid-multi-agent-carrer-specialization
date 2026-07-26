import json
import logging
import re
from typing import Any, Dict, List, Tuple

from app.profile_student_attribute.schema import (
    ProfileStudentAttributeCreate,
)
from app.profile_student_attribute.utils import decrypt_if_sensitive

logger = logging.getLogger(__name__)


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


def parse_attributes_from_response(response_text: str) -> Tuple[str, List[Dict[str, Any]]]:
    pattern = r"---ATTRIBUTES---\s*(.*?)\s*---END ATTRIBUTES---"
    match = re.search(pattern, response_text, re.DOTALL)
    if not match:
        logger.warning("ATTRIBUTES_BLOCK_NOT_FOUND | returning empty")
        return response_text.strip(), []

    block = match.group(1).strip()
    clean_text = re.sub(pattern, "", response_text, flags=re.DOTALL).strip()

    block = re.sub(r"^```(?:json)?\s*|\s*```$", "", block, flags=re.MULTILINE).strip()

    start_idx = -1
    for ch in ("[", "{"):
        idx = block.find(ch)
        if idx != -1 and (start_idx == -1 or idx < start_idx):
            start_idx = idx
    if start_idx > 0:
        block = block[start_idx:]

    try:
        data = json.loads(block)
    except json.JSONDecodeError as exc:
        logger.warning("ATTRIBUTES_BLOCK_PARSE_FAILED | error=%s | block=%s", exc, block)
        return clean_text, []

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        logger.warning("ATTRIBUTES_BLOCK_NOT_LIST | type=%s", type(data))
        return clean_text, []

    return clean_text, data


def build_attribute_creates(
    parsed_items: List[Dict[str, Any]],
    existing_keys: set,
) -> List[ProfileStudentAttributeCreate]:
    creates: List[ProfileStudentAttributeCreate] = []
    for parsed in parsed_items:
        category = parsed.get("category_name", "general")
        fields = parsed.get("fields", {})

        if not isinstance(fields, dict):
            logger.warning("ATTRIBUTES_FIELDS_NOT_DICT | category=%s | type=%s", category, type(fields))
            continue

        if not fields:
            logger.warning("ATTRIBUTES_FIELDS_EMPTY | category=%s", category)
            continue

        for cat, key, value in flatten_category(category, fields):
            if key in existing_keys:
                logger.info("ATTRIBUTE_ALREADY_EXISTS | key=%s | skipping", key)
                continue
            if value is None or value == "":
                continue
            creates.append(
                ProfileStudentAttributeCreate(
                    category_name=cat,
                    key=key,
                    value=str(value),
                )
            )
    return creates
