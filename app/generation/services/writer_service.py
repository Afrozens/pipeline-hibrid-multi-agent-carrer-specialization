import logging
from pathlib import Path
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables.base import RunnableConfig
from langsmith import traceable

from app.core.config import get_settings
from app.generation.constants import (
    CATEGORY_ORDER,
    TRACE_NAME_WRITER,
    TRACE_TAGS_WRITER,
)
from app.generation.schemas.agent_pipeline import (
    FieldContentError,
    PipelineState,
    WriterInput,
)
from app.generation.tool.write_tool import make_close_tool
from app.generation.utils.formatting import (
    format_collected_fields,
    format_missing_fields,
)

settings = get_settings()
logger = logging.getLogger(__name__)

_WRITER_PROMPT_PATH = Path(__file__).resolve().parent.parent / "system_prompts" / "writer.md"


def _load_writer_prompt() -> str:
    return _WRITER_PROMPT_PATH.read_text(encoding="utf-8")


def _format_content_errors(
    content_errors: Dict[str, Any],
) -> str:
    if not content_errors:
        return "  (none)"
    lines = []
    for cat in CATEGORY_ORDER:
        if cat not in content_errors or not content_errors[cat]:
            continue
        lines.append(f"  [{cat}]")
        _format_content_errors_nested(lines, content_errors[cat], indent=4)
    return "\n".join(lines) if lines else "  (none)"


def _format_content_errors_nested(
    lines: List[str], errors: Dict[str, Any], indent: int = 0
) -> None:
    prefix = " " * indent
    for k, v in errors.items():
        if isinstance(v, dict) and "error" in v:
            err = FieldContentError.model_validate(v)
            example = f" (e.g. {err.example_valid}, not {err.example_invalid})" if err.example_valid and err.example_invalid else ""
            lines.append(f"{prefix}{k}: {err.error}{example}")
        elif isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            _format_content_errors_nested(lines, v, indent + 2)


def _unflatten_attributes(
    attributes: List[Any],
) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for attr in attributes:
        category = attr.category_name
        keys = attr.key.split(".")
        value = attr.value

        current = result.setdefault(category, {})
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value
    return result


def _build_writer_input(state: PipelineState) -> WriterInput:
    collected_dict = _unflatten_attributes(state.collected_attributes)
    collected_summary = format_collected_fields(collected_dict)

    missing = state.validation.missing if state.validation else {}
    content_errors = state.validation.content_errors if state.validation else {}

    return WriterInput(
        conversation_history=state.conversation_history,
        current_category=state.current_category,
        collected_summary=collected_summary,
        missing_fields=missing,
        content_errors=content_errors,
        next_field_to_ask=state.next_field_to_ask,
        profile_complete=state.profile_complete,
    )


def _build_writer_messages(writer_input: WriterInput) -> List[SystemMessage | HumanMessage | AIMessage]:
    system_prompt = _load_writer_prompt()
    formatted = system_prompt.format(
        current_category=writer_input.current_category,
        collected_summary=writer_input.collected_summary,
        missing_fields=format_missing_fields(writer_input.missing_fields),
        content_errors=_format_content_errors(writer_input.content_errors),
        next_field_to_ask=writer_input.next_field_to_ask or "(none — profile may be complete)",
        profile_complete="yes" if writer_input.profile_complete else "no",
    )

    messages: List[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=formatted)
    ]

    for entry in writer_input.conversation_history:
        role = entry.get("role")
        content = entry.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    return messages


@traceable(name=TRACE_NAME_WRITER, tags=TRACE_TAGS_WRITER)
async def writer_node(state: PipelineState, config: RunnableConfig) -> Dict[str, Any]:
    logger.info(
        "WRITER_START | category=%s | profile_complete=%s | turns=%d",
        state.current_category,
        state.profile_complete,
        len(state.conversation_history),
    )

    writer_input = _build_writer_input(state)
    messages = _build_writer_messages(writer_input)

    try:
        db = config["configurable"]["db"]
        conversation_id = config["configurable"]["conversation_id"]
        close_tool = make_close_tool(db=db, conversation_id=conversation_id)
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        ).bind_tools([close_tool])
        response = await llm.ainvoke(messages)
        if response.tool_calls:
            assistant_text = ""
            should_close = False
            for tool_call in response.tool_calls:
                if tool_call["name"] == "close_conversation":
                    assistant_text = await close_tool.ainvoke(tool_call)
                    should_close = True
                    break
        else:
            assistant_text = response.content or ""
            should_close = False
    except Exception as exc:
        logger.error("WRITER_LLM_FAILED | error=%s", exc, exc_info=True)
        assistant_text = (
            "I'm sorry, I encountered a technical issue. "
            "Could you please repeat that?"
        )
        should_close = False

    logger.info(
        "WRITER_DONE | response_length=%d | should_close=%s",
        len(assistant_text),
        should_close,
    )

    return {
        "assistant_response": assistant_text,
        "raw_llm_response": assistant_text,
        "should_close": should_close,
    }
