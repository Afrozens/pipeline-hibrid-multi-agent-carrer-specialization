import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.profile_student.utils.field_content_rules import FIELD_CONTENT_RULES


def _get_nested_value(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _prune_required(
    required: Dict[str, Any],
    present_root: Dict[str, Any],
    path: List[str] = None,
) -> Dict[str, Any]:
    if path is None:
        path = []

    pruned: Dict[str, Any] = {}
    for k, v in required.items():
        if k == "options":
            continue

        current_path = path + [k]

        if isinstance(v, dict):
            if k == "if_bachelor_or_higher":
                degree = _get_nested_value(present_root, ["education", "highest_degree", "type"])
                if degree not in ("bachelor", "master", "phd"):
                    continue

            elif k == "if_experienced":
                years = _get_nested_value(present_root, ["experience", "years_of_experience"])
                if years is None or years == 0 or years == "0":
                    continue

            pruned[k] = _prune_required(v, present_root, current_path)
        else:
            if v is not None:
                continue
            pruned[k] = v

    return pruned


class CriticalFieldValidator:
    def __init__(
        self,
        file_path: Path | None = None,
        json_key: str = "mandatory_fields",
        encoding: str = "utf-8",
    ) -> None:
        self._file_path: Path = file_path or self._default_path()
        self._json_key: str = json_key
        self._encoding: str = encoding
        self._critical_fields_cache: Optional[Dict[str, Dict[str, Any]]] = None

    @staticmethod
    def _default_path() -> Path:
        return Path(__file__).resolve().parents[2] / "docs" / "career_fields.json"

    def get_critical_fields_path(self) -> Path:
        return self._file_path

    def load_critical_fields(self) -> Dict[str, Dict[str, Any]]:
        if self._critical_fields_cache is not None:
            return self._critical_fields_cache

        path = self.get_critical_fields_path()
        if not path.exists():
            raise FileNotFoundError(f"Critical fields definition not found at {path}")

        with open(path, "r", encoding=self._encoding) as f:
            data = json.load(f)

        self._critical_fields_cache = data.get(self._json_key, {})
        return self._critical_fields_cache

    @staticmethod
    def _normalize_category(name: str) -> str:
        return name.lower().replace(" ", "_").replace("-", "_")

    def _match_category(
        self, extracted: Dict[str, Dict[str, Any]], required_name: str
    ) -> Optional[Dict[str, Any]]:
        normalized_required = self._normalize_category(required_name)
        for ext_name in extracted:
            normalized_ext = self._normalize_category(ext_name)
            if normalized_ext == normalized_required:
                return extracted[ext_name]
        return None

    def _validate_recursive(
        self,
        required: Dict[str, Any],
        present: Dict[str, Any],
        prefix: str = "",
    ) -> List[str]:
        missing: List[str] = []
        for k, v in required.items():
            key_path = f"{prefix}{k}"
            if isinstance(v, dict):
                if "options" in v and isinstance(v.get("options"), str):
                    if k not in present or present[k] is None or present[k] == "":
                        missing.append(key_path)
                else:
                    sub_present = (
                        present.get(k, {}) if isinstance(present.get(k), dict) else {}
                    )
                    sub_missing = self._validate_recursive(
                        v, sub_present, f"{key_path}."
                    )
                    missing.extend(sub_missing)
            else:
                if k not in present or present[k] is None or present[k] == "":
                    missing.append(key_path)
        return sorted(missing)

    def _collect_all_keys(self, d: Dict[str, Any], prefix: str = "") -> List[str]:
        keys: List[str] = []
        for k, v in d.items():
            key_path = f"{prefix}{k}"
            if isinstance(v, dict):
                if "options" in v and isinstance(v.get("options"), str):
                    keys.append(key_path)
                else:
                    keys.extend(self._collect_all_keys(v, f"{key_path}."))
            else:
                keys.append(key_path)
        return sorted(keys)

    def validate_extracted_fields(
        self,
        extracted: Dict[str, Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        critical = self.load_critical_fields()
        missing: Dict[str, List[str]] = {}

        for cat_name, required_fields in critical.items():
            extracted_cat = self._match_category(extracted, cat_name)
            if extracted_cat is None:
                pruned_required = _prune_required(required_fields, extracted)
                missing[cat_name] = self._collect_all_keys(pruned_required)
                continue

            pruned_required = _prune_required(required_fields, extracted)
            missing_keys = self._validate_recursive(pruned_required, extracted_cat)
            if missing_keys:
                missing[cat_name] = missing_keys

        return missing

    @staticmethod
    def _rule_not_empty(value: Any, rule: Dict[str, Any]) -> Optional[str]:
        if value is None or str(value).strip() == "":
            return rule.get("message", "Cannot be empty")
        return None

    @staticmethod
    def _rule_not_numeric(value: Any, rule: Dict[str, Any]) -> Optional[str]:
        s = str(value).strip()
        if s and s.replace(".", "", 1).replace("-", "", 1).isdigit():
            return rule.get("message", "Cannot be purely numeric")
        return None

    @staticmethod
    def _rule_min_words(value: Any, rule: Dict[str, Any]) -> Optional[str]:
        s = str(value).strip()
        words = [w for w in s.split() if w]
        if len(words) < rule.get("count", 1):
            return rule.get("message", f"Must contain at least {rule.get('count', 1)} words")
        return None

    @staticmethod
    def _rule_regex(value: Any, rule: Dict[str, Any]) -> Optional[str]:
        pattern = rule.get("pattern", "")
        if not re.match(pattern, str(value)):
            return rule.get("message", "Invalid format")
        return None

    @staticmethod
    def _rule_date(value: Any, rule: Dict[str, Any]) -> Optional[str]:
        s = str(value).strip()
        for fmt in rule.get("formats", ["%Y-%m-%d"]):
            try:
                dt = datetime.strptime(s, fmt).date()
                today = date.today()
                age = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
                min_age = rule.get("min_age")
                max_age = rule.get("max_age")
                if min_age is not None and age < min_age:
                    return rule.get("message", f"Must be at least {min_age} years old")
                if max_age is not None and age > max_age:
                    return rule.get("message", f"Must be at most {max_age} years old")
                return None
            except ValueError:
                continue
        return rule.get("message", "Invalid date format")

    @staticmethod
    def _rule_number_range(value: Any, rule: Dict[str, Any]) -> Optional[str]:
        try:
            num = float(value)
        except (ValueError, TypeError):
            return rule.get("message", "Must be a valid number")
        min_val = rule.get("min")
        max_val = rule.get("max")
        if min_val is not None and num < min_val:
            return rule.get("message", f"Must be at least {min_val}")
        if max_val is not None and num > max_val:
            return rule.get("message", f"Must be at most {max_val}")
        return None

    @staticmethod
    def _rule_enum(value: Any, rule: Dict[str, Any]) -> Optional[str]:
        allowed = rule.get("values", [])
        s = str(value).strip()
        if s not in allowed:
            return rule.get("message", f"Must be one of: {', '.join(allowed)}")
        return None

    _RULE_REGISTRY: Dict[str, Any] = {
        "not_empty": _rule_not_empty,
        "not_numeric": _rule_not_numeric,
        "min_words": _rule_min_words,
        "regex": _rule_regex,
        "date": _rule_date,
        "number_range": _rule_number_range,
        "enum": _rule_enum,
    }

    def _apply_rule(self, value: Any, rule: Dict[str, Any]) -> Optional[str]:
        rule_type = rule.get("type")
        handler = self._RULE_REGISTRY.get(rule_type)
        if handler is None:
            return None
        return handler(value, rule)

    def validate_field_content(
        self, field_path: str, value: Any
    ) -> Optional[Dict[str, Any]]:
        definition = FIELD_CONTENT_RULES.get(field_path)
        if not definition:
            return None

        for rule in definition.get("rules", []):
            error_msg = self._apply_rule(value, rule)
            if error_msg:
                return {
                    "error": error_msg,
                    "example_valid": definition.get("example_valid"),
                    "example_invalid": definition.get("example_invalid"),
                }
        return None

    def _validate_content_recursive(
        self, data: Dict[str, Any], prefix: str = ""
    ) -> Dict[str, Any]:
        errors: Dict[str, Any] = {}
        for k, v in data.items():
            current_path = f"{prefix}{k}"
            if isinstance(v, dict):
                sub = self._validate_content_recursive(v, f"{current_path}.")
                if sub:
                    errors[k] = sub
            else:
                if v is not None and v != "":
                    err = self.validate_field_content(current_path, v)
                    if err:
                        errors[k] = err
        return errors

    def validate_extracted_content(
        self, extracted: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for category, fields in extracted.items():
            cat_errors = self._validate_content_recursive(fields, f"{category}.")
            if cat_errors:
                result[category] = cat_errors
        return result

    def validate_extracted_fields_complete(
        self, extracted: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "missing": self.validate_extracted_fields(extracted),
            "content_errors": self.validate_extracted_content(extracted),
        }


_default_validator = CriticalFieldValidator()


def load_critical_fields() -> Dict[str, Dict[str, Any]]:
    return _default_validator.load_critical_fields()


def validate_extracted_fields(
    extracted: Dict[str, Dict[str, Any]],
) -> Dict[str, List[str]]:
    return _default_validator.validate_extracted_fields(extracted)


def validate_extracted_content(
    extracted: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    return _default_validator.validate_extracted_content(extracted)


def validate_extracted_fields_complete(
    extracted: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    return _default_validator.validate_extracted_fields_complete(extracted)
