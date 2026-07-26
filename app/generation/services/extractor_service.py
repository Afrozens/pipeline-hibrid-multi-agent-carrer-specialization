import logging
from pathlib import Path
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langsmith import traceable

from app.core.config import get_settings
from app.generation.constants import (
    TRACE_NAME_EXTRACTOR,
    TRACE_TAGS_EXTRACTOR,
)
from app.generation.schemas.agent_pipeline import ExtractorOutput, PipelineState

settings = get_settings()
logger = logging.getLogger(__name__)

_EXTRACTOR_PROMPT_PATH = Path(__file__).resolve().parent.parent / "system_prompts" / "extractor.md"


def _load_extractor_prompt() -> str:
    return _EXTRACTOR_PROMPT_PATH.read_text(encoding="utf-8")


def _build_extractor_messages(
    conversation_history: List[Dict[str, str]],
) -> List[SystemMessage | HumanMessage | AIMessage]:
    prompt = _load_extractor_prompt()
    messages: List[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=prompt)
    ]
    for entry in conversation_history:
        role = entry.get("role")
        content = entry.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


@traceable(name=TRACE_NAME_EXTRACTOR, tags=TRACE_TAGS_EXTRACTOR)
async def extractor_node(state: PipelineState) -> Dict[str, Any]:
    logger.info(
        "EXTRACTOR_START | turns=%d",
        len(state.conversation_history),
    )

    messages = _build_extractor_messages(state.conversation_history)

    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_EXTRACTOR_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.0,
        ).with_structured_output(ExtractorOutput, method="function_calling")

        result = await llm.ainvoke(messages)
        raw_text = result.model_dump_json()
    except Exception as exc:
        logger.error("EXTRACTOR_LLM_FAILED | error=%s", exc, exc_info=True)
        result = ExtractorOutput(extracted={})
        raw_text = str(exc)

    logger.info(
        "EXTRACTOR_DONE | extracted_categories=%s",
        list(result.extracted.keys()) if result.extracted else "none",
    )

    return {
        "extracted_raw": result,
        "raw_llm_response": raw_text,
    }
