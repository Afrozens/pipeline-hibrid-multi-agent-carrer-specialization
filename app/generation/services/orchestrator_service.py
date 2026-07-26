import logging
from typing import Any, Dict, List, Optional, Tuple

from app.profile_student.utils.critical_field_validator import (
    CriticalFieldValidator,
)
from app.profile_student_attribute.schema import ProfileStudentAttributeCreate
from app.generation.constants import CATEGORY_ORDER
from app.generation.schemas.agent_pipeline import (
    MapperOutput,
    PipelineState,
    ValidationResult,
)
from app.generation.utils.formatting import (
    determine_current_category,
    flatten_for_attributes,
)

logger = logging.getLogger(__name__)


def _merge_nested(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _merge_nested(base[k], v)
        else:
            base[k] = v
    return base


def _build_merged_extraction(
    collected_attributes: List[ProfileStudentAttributeCreate],
    normalized_new: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for attr in collected_attributes:
        category = attr.category_name
        keys = attr.key.split(".")
        current = merged.setdefault(category, {})
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = attr.value

    for category, fields in normalized_new.items():
        cat_dict = merged.setdefault(category, {})
        _merge_nested(cat_dict, fields)

    return merged


def _determine_next_field(
    missing: Dict[str, List[str]], current_category: str
) -> Optional[str]:
    cat_missing = missing.get(current_category, [])
    return cat_missing[0] if cat_missing else None


def _is_category_complete(missing: Dict[str, List[str]], category: str) -> bool:
    return not missing.get(category)


def _is_profile_complete(missing: Dict[str, List[str]]) -> bool:
    return not any(missing.values())


def orchestrator_node(state: PipelineState) -> Dict[str, Any]:
    normalized_new = (
        state.extracted_normalized.normalized
        if state.extracted_normalized
        else {}
    )

    logger.info(
        "ORCHESTRATOR_START | new_categories=%s | history_attrs=%d",
        list(normalized_new.keys()) if normalized_new else "none",
        len(state.collected_attributes),
    )

    merged = _build_merged_extraction(
        state.collected_attributes,
        normalized_new,
    )

    validator = CriticalFieldValidator()
    validation = validator.validate_extracted_fields_complete(merged)

    missing = validation.get("missing", {})
    current_category = determine_current_category(missing)
    next_field = _determine_next_field(missing, current_category)
    category_complete = _is_category_complete(missing, current_category)
    profile_complete = _is_profile_complete(missing)

    all_attributes = flatten_for_attributes(merged)

    seen: set = set()
    deduped_attributes: List[ProfileStudentAttributeCreate] = []
    for attr in reversed(all_attributes):
        key = (attr.category_name, attr.key)
        if key not in seen:
            seen.add(key)
            deduped_attributes.append(attr)
    deduped_attributes.reverse()

    existing = {(a.category_name, a.key): a.value for a in state.collected_attributes}
    attributes_to_persist = [
        attr for attr in deduped_attributes
        if (attr.category_name, attr.key) not in existing
        or existing[(attr.category_name, attr.key)] != attr.value
    ]

    logger.info(
        "ORCHESTRATOR_DONE | category=%s | next=%s | cat_complete=%s | profile_complete=%s | attrs_total=%d | attrs_to_persist=%d",
        current_category,
        next_field,
        category_complete,
        profile_complete,
        len(deduped_attributes),
        len(attributes_to_persist),
    )

    return {
        "validation": ValidationResult(
            missing=missing,
            content_errors=validation.get("content_errors", {}),
        ),
        "current_category": current_category,
        "next_field_to_ask": next_field,
        "category_complete": category_complete,
        "profile_complete": profile_complete,
        "collected_attributes": deduped_attributes,
        "attributes_to_persist": attributes_to_persist,
    }
