import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.generation.constants.paths import CAREER_SPECIALIZATIONS_PATH

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


async def _fetch_market_trends() -> str:
    """Fetch current market trends via configured web search provider."""
    searches = [
        "top software engineering specializations in demand 2026",
        "best tech careers to learn 2026",
        "highest paying tech jobs 2026",
        "emerging technologies hiring trends 2026",
    ]
    results: List[str] = []
    for query in searches:
        try:
            from app.core.tools import web_search
            result = await web_search(query)
            results.append(result)
        except ImportError:
            logger.warning("MARKET_TRENDS_SKIP | web_search tool not available")
            break
        except Exception:
            logger.warning("MARKET_TRENDS_SEARCH_FAILED | query=%s", query, exc_info=True)
            continue

    return "\n\n".join(results) if results else "Sin datos de tendencias disponibles"


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
        HumanMessage(content="Por favor, genera mis recomendaciones de carrera basadas en mi perfil."),
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
            "He completado el análisis de tu perfil, pero tuve un problema técnico "
            "al generar las recomendaciones. Por favor, intenta de nuevo más tarde."
        )
