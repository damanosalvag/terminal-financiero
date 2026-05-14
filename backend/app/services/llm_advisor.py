"""
Servicio de IA Estratégica usando DeepSeek API.
Actúa como analista institucional para generar narrativas de inversión.
"""

import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_NARRATIVE_PROMPT = (
    "Eres un analista financiero institucional senior especializado en swing trading.\n\n"
    "Analiza el ticker {ticker} y las siguientes noticias recientes:\n\n"
    "{news_summary}\n\n"
    "Debes devolver UNICAMENTE un objeto JSON valido con esta estructura exacta:\n"
    "{{\n"
    '    "business_summary": "1 frase corta describiendo el negocio principal en espanol",\n'
    '    "competitors": ["TICKER1", "TICKER2", "TICKER3"],\n'
    '    "supply_chain": {{\n'
    '        "upstream_suppliers": ["Proveedor A", "Proveedor B", "Proveedor C"],\n'
    '        "downstream_clients": ["Cliente A", "Cliente B", "Cliente C"]\n'
    "    }},\n"
    '    "macro_accelerators": ["Factor macro 1", "Factor macro 2"],\n'
    '    "news_analysis": ["Bullet 1 sobre impacto", "Bullet 2 sobre impacto", "Bullet 3 sobre impacto"]\n'
    "}}\n\n"
    "Reglas estrictas:\n"
    "- business_summary: maximo 1 frase en espanol, directa.\n"
    "- competitors: 3 tickers reales de competidores directos (solo simbolos).\n"
    "- supply_chain: 3 proveedores clave y 3 clientes clave en espanol.\n"
    "- macro_accelerators: 2 factores macro que mueven el precio de este activo.\n"
    "- news_analysis: 2-3 bullets en espanol analizando las noticias provistas y su probable impacto en el precio a corto plazo.\n"
    "- No incluyas texto fuera del JSON.\n"
    "You MUST return your response in valid JSON format."
)


def get_strategic_intel(ticker: str, news: list[dict[str, str | None]]) -> dict[str, Any]:
    """
    Genera inteligencia estratégica usando DeepSeek API.

    Args:
        ticker: Símbolo bursátil.
        news: Lista de noticias recientes (title, publisher, link).

    Returns:
        Diccionario con business_summary, competitors, supply_chain, macro_accelerators, news_analysis.

    Raises:
        ValueError: Si falta la API key, openai no está instalado, o DeepSeek falla.
    """
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is missing in settings.")

    try:
        from openai import OpenAI
    except ImportError:
        raise ValueError("openai package missing. Install with: pip install openai")

    news_lines = []
    for i, n in enumerate(news[:5], 1):
        title = n.get("title", "Sin título")
        news_lines.append(f"{i}. {title}")
    news_summary = "\n".join(news_lines) if news_lines else "No hay noticias recientes disponibles."

    prompt = _NARRATIVE_PROMPT.format(ticker=ticker, news_summary=news_summary)

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1000,
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise ValueError("DeepSeek returned an empty response.")

        cleaned = raw_content.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as parse_error:
            raise ValueError(
                f"LLM JSON parsing failed. Error: {parse_error}. Raw output: {cleaned[:500]}"
            ) from parse_error

    except ValueError:
        raise
    except Exception as exc:
        logger.exception("DeepSeek API call failed for ticker=%s: %s", ticker, exc)
        raise


_NEWS_INTEL_PROMPT = (
    "Eres un analista macroeconómico implacable. Analiza las siguientes noticias del ticker {ticker} "
    "con un enfoque materialista y estructural. Prioriza impactos tangibles sobre la economía real: "
    "cadenas de suministro físicas, commodities, rearme militar, infraestructura energética, "
    "y capacidad industrial. Ignora el ruido superficial de relaciones públicas.\n\n"
    "Noticias recientes:\n{news_summary}\n\n"
    "Devuelve UNICAMENTE un objeto JSON valido con esta estructura:\n"
    '{{"sentiment": "Bullish"|"Bearish"|"Neutral", '
    '"impact_summary": "2 frases cortas maximo describiendo el impacto tangible.", '
    '"macro_driver": "2-3 palabras, ej: Cadena de Suministro, Costos Energéticos, Rearme"}}\n'
    "IMPORTANTE: Los campos 'impact_summary' y 'macro_driver' deben estar SIEMPRE en español. "
    "El campo 'sentiment' debe ser exactamente 'Bullish', 'Bearish' o 'Neutral' (en inglés, sin traducir).\n"
    "You MUST return your response in valid JSON format."
)


def analyze_portfolio_news(ticker: str, news_items: list[dict[str, str | None]]) -> dict[str, Any] | None:
    """
    Analiza noticias recientes de un ticker con un enfoque macro-materialista.
    Usa DeepSeek para extraer sentimiento, resumen de impacto y driver macro.

    Returns:
        Dict con sentiment, impact_summary, macro_driver. None si no hay API key.
    """
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    news_lines = []
    for i, n in enumerate(news_items[:3], 1):
        title = n.get("title", "Sin título")
        news_lines.append(f"{i}. {title}")
    news_summary = "\n".join(news_lines) if news_lines else "No hay noticias recientes."

    prompt = _NEWS_INTEL_PROMPT.format(ticker=ticker, news_summary=news_summary)

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=400,
        )

        raw = response.choices[0].message.content
        if not raw:
            return None

        cleaned = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)

    except Exception:
        return None
