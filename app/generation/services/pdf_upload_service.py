import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import get_settings
from app.generation.utils.formatting import format_collected_fields, format_missing_fields

settings = get_settings()
logger = logging.getLogger(__name__)

_CV_UPLOAD_PATH = Path(__file__).resolve().parent.parent / "system_prompts" / "cv_upload.md"


def _load_cv_upload_prompt() -> str:
    return _CV_UPLOAD_PATH.read_text(encoding="utf-8")


async def extract_fields_from_pdf_markdown(markdown_text: str) -> Dict[str, Dict[str, Any]]:
    prompt = _load_cv_upload_prompt()

    parts = prompt.split("---CV MARKDOWN CONTENT---")
    if len(parts) >= 2:
        extraction_section = parts[0]
        system_prompt = extraction_section + f"\n\n---CV MARKDOWN CONTENT---\n{markdown_text}\n---END CV MARKDOWN---\n" + parts[1].split("---END CV MARKDOWN---")[-1]
    else:
        system_prompt = prompt

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Extract the fields from the CV markdown content above."),
    ]

    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.1,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        response = await llm.ainvoke(messages)
        content = response.content or "{}"

        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        extracted = json.loads(content)
        if not isinstance(extracted, dict):
            logger.warning("PDF_EXTRACTION_NON_DICT | type=%s", type(extracted))
            return {}
        return extracted
    except json.JSONDecodeError as exc:
        logger.error("PDF_EXTRACTION_JSON_FAILED | error=%s", exc, exc_info=True)
        return {}
    except Exception as exc:
        logger.error("PDF_EXTRACTION_LLM_FAILED | error=%s", exc, exc_info=True)
        return {}


async def generate_pdf_upload_response(
    filename: str,
    collected: Dict[str, Dict[str, Any]],
    missing: Dict[str, List[str]],
    current_category: str,
    history: List[Dict[str, str]],
) -> str:
    collected_summary = format_collected_fields(collected)
    missing_summary = format_missing_fields(missing)

    prompt = _load_cv_upload_prompt()

    parts = prompt.split("## CV_UPLOAD_PROMPT")
    upload_prompt = parts[-1] if len(parts) >= 2 else prompt

    system_prompt = upload_prompt.format(
        filename=filename,
        collected_summary=collected_summary,
        missing_summary=missing_summary,
        current_category=current_category,
    )

    messages = [SystemMessage(content=system_prompt)]
    for entry in history:
        if entry["role"] == "user":
            messages.append(HumanMessage(content=entry["content"]))

    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        )
        response = await llm.ainvoke(messages)
        return response.content or ""
    except Exception as exc:
        logger.error("PDF_UPLOAD_LLM_FAILED | error=%s", exc, exc_info=True)
        return (
            f"I've processed your CV **{filename}**. "
            f"The data has been saved to your profile. "
            f"Let me know if you need help completing the remaining information."
        )
