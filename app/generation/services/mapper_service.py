import json
import logging
from pathlib import Path
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable

from app.core.config import get_settings
from app.generation.constants import (
    TRACE_NAME_MAPPER,
    TRACE_TAGS_MAPPER,
)
from app.generation.schemas.agent_pipeline import MapperOutput, PipelineState

settings = get_settings()
logger = logging.getLogger(__name__)

_MAPPER_PROMPT_PATH = Path(__file__).resolve().parent.parent / "system_prompts" / "mapper.md"


def _load_mapper_prompt() -> str:
    return _MAPPER_PROMPT_PATH.read_text(encoding="utf-8")


@traceable(name=TRACE_NAME_MAPPER, tags=TRACE_TAGS_MAPPER)
async def mapper_node(state: PipelineState) -> Dict[str, Any]:
    raw_extraction = state.extracted_raw.extracted if state.extracted_raw else {}

    if not raw_extraction:
        logger.info("MAPPER_SKIP | no raw data to normalize")
        return {
            "extracted_normalized": MapperOutput(
                normalized={}, mapping_log=[]
            ),
        }

    logger.info(
        "MAPPER_START | categories=%s",
        list(raw_extraction.keys()),
    )

    prompt = _load_mapper_prompt()
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=str(raw_extraction)),
    ]

    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_EXTRACTOR_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.0,
        )

        raw_response = await llm.ainvoke(messages)
        data = json.loads(raw_response.content)

        if isinstance(data.get("normalized"), dict) and "mapping_log" in data["normalized"]:
            data["mapping_log"] = data["normalized"].pop("mapping_log")

        result = MapperOutput.model_validate(data)
    except Exception as exc:
        logger.error("MAPPER_LLM_FAILED | error=%s", exc, exc_info=True)
        result = MapperOutput(
            normalized=raw_extraction,
            mapping_log=[],
        )

    logger.info(
        "MAPPER_DONE | mappings_applied=%d",
        len(result.mapping_log),
    )

    return {
        "extracted_normalized": result,
    }
