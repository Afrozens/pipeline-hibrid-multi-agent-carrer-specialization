from typing import Any, Dict, List

from app.generation.constants import CATEGORY_ORDER
from app.profile_student_attribute.schema import (
    ProfileStudentAttributeCreate,
)


def format_collected_fields(collected: Dict[str, Dict[str, Any]]) -> str:
    if not collected:
        return "  (none)"
    lines: List[str] = []
    for cat in CATEGORY_ORDER:
        if cat not in collected or not collected[cat]:
            continue
        lines.append(f"  [{cat}]")
        _format_nested(lines, collected[cat], indent=4)
    return "\n".join(lines) if lines else "  (none)"


def _format_nested(lines: List[str], data: Dict[str, Any], indent: int = 0) -> None:
    prefix = " " * indent
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            _format_nested(lines, v, indent + 2)
        else:
            lines.append(f"{prefix}{k}: {v}")


def format_missing_fields(missing: Dict[str, List[str]]) -> str:
    if not missing:
        return "  (all complete!)"
    lines: List[str] = []
    for cat in CATEGORY_ORDER:
        if cat not in missing or not missing[cat]:
            continue
        lines.append(f"  [{cat}]")
        for key in missing[cat]:
            lines.append(f"    - {key}")
    return "\n".join(lines) if lines else "  (all complete!)"


def determine_current_category(missing: Dict[str, List[str]]) -> str:
    for cat in CATEGORY_ORDER:
        if cat in missing and missing[cat]:
            return cat
    return CATEGORY_ORDER[-1]


def flatten_for_attributes(
    data: Dict[str, Dict[str, Any]],
) -> List[ProfileStudentAttributeCreate]:
    creates: List[ProfileStudentAttributeCreate] = []

    def _walk(category: str, node: Dict[str, Any], prefix: str = "") -> None:
        for k, v in node.items():
            key = f"{prefix}{k}" if prefix else k
            if isinstance(v, dict):
                _walk(category, v, f"{key}.")
            elif v is not None and v != "":
                creates.append(
                    ProfileStudentAttributeCreate(
                        category_name=category,
                        key=key,
                        value=str(v),
                    )
                )

    for category, fields in data.items():
        _walk(category, fields)

    return creates
