import json
import logging
import re
import httpx
from pathlib import Path
from typing import Any, List
from uuid import UUID

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.generation.constants.paths import CAREER_SPECIALIZATIONS_PATH
from app.generation.constants.tracing import (
    TRACE_NAME_CAREER_RECOMMENDATION,
    TRACE_TAGS_CAREER_RECOMMENDATION,
)

settings = get_settings()
logger = logging.getLogger(__name__)

_MARKET_TRENDS_PATH = Path(__file__).resolve().parent.parent / "system_prompts" / "market_trends.md"
_CAREER_RECOMMENDATION_PATH = Path(__file__).resolve().parent.parent / "system_prompts" / "career_recommendation.md"


def _load_market_trends_prompt() -> str:
    return _MARKET_TRENDS_PATH.read_text(encoding="utf-8")


def _load_career_recommendation_prompt() -> str:
    return _CAREER_RECOMMENDATION_PATH.read_text(encoding="utf-8")


def _load_specializations() -> str:
    try:
        with open(CAREER_SPECIALIZATIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error("SPECIALIZATIONS_LOAD_FAILED | error=%s", exc)
        return "{}"


def _build_profile_summary(profile_attributes: List[Any]) -> str:
    lines: List[str] = []
    for attr in profile_attributes:
        if getattr(attr, "deleted_at", None) is not None:
            continue
        lines.append(f"  {attr.category_name}.{attr.key}: {attr.value}")
    return "\n".join(lines) if lines else "  (no profile data)"


async def _web_search(query: str) -> str:
    snippets = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            resp.raise_for_status()

            results = re.findall(
                r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>',
                resp.text,
                re.DOTALL,
            )
            for snippet in results[:5]:
                clean = re.sub(r"<[^>]+>", "", snippet).strip()
                if clean:
                    snippets.append(clean)

        logger.info("WEB_SEARCH_OK | query=%s | snippets=%d", query, len(snippets))
    except ImportError:
        logger.warning("WEB_SEARCH_SKIP | httpx not available")
    except Exception as exc:
        logger.warning("WEB_SEARCH_FAILED | query=%s | error=%s", query, exc)

    return "\n".join(snippets) if snippets else ""


async def _fetch_market_trends() -> str:
    searches = [
        "top software engineering specializations in demand 2026",
        "best tech careers to learn 2026",
        "highest paying tech jobs 2026",
        "emerging technologies hiring trends 2026",
    ]
    raw_parts: List[str] = []
    for query in searches:
        result = await _web_search(query)
        if result:
            raw_parts.append(f"Query: {query}\n{result}")

    if not raw_parts:
        return "No market trends data available."

    raw_text = "\n\n".join(raw_parts)
    system_prompt = _load_market_trends_prompt()

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                "Here are the raw web search results for current tech market trends:\n\n"
                f"{raw_text}\n\n"
                "Please analyze and return structured data about the most "
                "in-demand technology specializations based on these results."
            )
        ),
    ]

    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        )
        response = await llm.ainvoke(messages)
        result = response.content or ""
        logger.info("MARKET_TRENDS_LLM_OK | len=%d", len(result))
        return result
    except Exception as exc:
        logger.error("MARKET_TRENDS_LLM_FAILED | error=%s", exc, exc_info=True)
        return raw_text


@traceable(name=TRACE_NAME_CAREER_RECOMMENDATION, tags=TRACE_TAGS_CAREER_RECOMMENDATION)
async def generate_career_recommendations(
    profile_attributes: List[Any],
    db: AsyncSession,
    conversation_id: UUID,
) -> str:
    profile_summary = _build_profile_summary(profile_attributes)
    specializations = _load_specializations()

    market_trends = await _fetch_market_trends()

    recommendation_prompt = _load_career_recommendation_prompt()
    formatted_prompt = recommendation_prompt.format(
        profile_summary=profile_summary,
        specializations=specializations,
        market_trends=market_trends,
    )

    messages = [
        SystemMessage(content=formatted_prompt),
        HumanMessage(
            content=(
                "Please generate my career recommendations based on my profile."
            )
        ),
    ]

    try:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.5,
        )
        response = await llm.ainvoke(messages)
        return response.content or ""
    except Exception as exc:
        logger.error("RECOMMENDATION_LLM_FAILED | error=%s", exc, exc_info=True)
        return (
            "I've completed the analysis of your profile, but I encountered a technical "
            "issue while generating recommendations. Please try again later."
        )
