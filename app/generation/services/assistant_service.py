import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langsmith import traceable

from app.core.config import get_settings
from app.generation.constants import (
    TRACE_NAME_PROFILE_ASSISTANT,
    TRACE_TAGS_PROFILE_ASSISTANT,
)
from app.profile_student_attribute.schema import (
    ProfileStudentAttributeCreate,
)
from app.generation.utils import (
    unflatten_attributes,
    parse_attributes_from_response,
    build_attribute_creates,
)
from app.generation.utils.formatting import (
    format_collected_fields,
    format_missing_fields,
    determine_current_category,
)

settings = get_settings()
logger = logging.getLogger(__name__)

_PROFILE_ASSISTANT_PATH = Path(__file__).resolve().parent.parent / "system_prompts" / "profile_assistant.md"


def _load_profile_assistant_prompt() -> str:
    return _PROFILE_ASSISTANT_PATH.read_text(encoding="utf-8")


@traceable(name=TRACE_NAME_PROFILE_ASSISTANT, tags=TRACE_TAGS_PROFILE_ASSISTANT)
async def generate_profile_assistant_response(
    conversation_history: List[Dict[str, str]],
    profile_attributes,
    missing_fields: Dict[str, List[str]],
) -> Tuple[str, str, List[ProfileStudentAttributeCreate]]:
    collected = unflatten_attributes(profile_attributes)
    current_category = determine_current_category(missing_fields)
    missing_in_current = missing_fields.get(current_category, [])

    collected_str = format_collected_fields(collected)
    missing_current_str = (
        "\n".join(f"    - {k}" for k in missing_in_current)
        if missing_in_current
        else "    (none — category complete)"
    )
    all_missing_str = format_missing_fields(missing_fields)

    system_prompt = _load_profile_assistant_prompt()
    system_prompt = system_prompt.format(
        current_category=current_category,
        collected_fields=collected_str,
        missing_in_current=missing_current_str,
        all_missing=all_missing_str,
    )

    messages = [SystemMessage(content=system_prompt)]
    for entry in conversation_history:
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))
        elif entry["role"] == "assistant":
            messages.append(AIMessage(content=entry["content"]))

    logger.info(
        "PROFILE_ASSISTANT_GENERATE | category=%s | history_turns=%d | missing_in_current=%d",
        current_category,
        len(conversation_history),
        len(missing_in_current),
    )

    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        )
        response = await llm.ainvoke(messages)
        raw_text = response.content or ""
    except Exception as exc:
        logger.error("PROFILE_ASSISTANT_LLM_FAILED | error=%s", exc, exc_info=True)
        return (
            "I'm sorry, I encountered a technical issue. Could you please repeat that?",
            "I'm sorry, I encountered a technical issue. Could you please repeat that?",
            [],
        )

    logger.info("LLM_RAW_RESPONSE | %s", raw_text)
    clean_text, parsed = parse_attributes_from_response(raw_text)

    existing_keys = {attr.key for attr in profile_attributes if getattr(attr, "deleted_at", None) is None}
    attribute_creates = build_attribute_creates(parsed, existing_keys)

    logger.info(
        "PROFILE_ASSISTANT_DONE | text_length=%d | new_attributes=%d",
        len(clean_text),
        len(attribute_creates),
    )

    return clean_text, raw_text, attribute_creates
