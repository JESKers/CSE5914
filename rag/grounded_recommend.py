"""Ground recommendation text in Elasticsearch vehicles and NHTSA vPIC evidence."""
from __future__ import annotations

import os
import re
from typing import Any

from langchain_core.prompts import PromptTemplate

from search import vpic

from .ollama_utils import get_chat_model


PROMPT = PromptTemplate.from_template("""You are a grounded vehicle recommendation assistant.
Answer the user's request using ONLY the evidence below.
Every vehicle claim must cite its evidence token exactly as [car:ID].
Do not invent safety, reliability, availability, price, or specifications.
Treat vPIC status 'not_found' as unverified, not proof that the vehicle is invalid.
If the evidence is insufficient, say so. Use at most 120 words.

User request: {query}

Retrieved evidence:
{context}
""")


def enrich_with_vpic(cars: list[dict], max_lookups: int | None = None) -> list[dict]:
    """Attach vPIC evidence to top ES results with a strict request budget."""
    limit = max_lookups if max_lookups is not None else int(os.getenv("VPIC_RECOMMEND_LOOKUPS", "3"))
    cache: dict[tuple[str, str, int | None], dict[str, Any]] = {}
    enriched = []
    for car in cars:
        row = dict(car)
        key = (str(car.get("make", "")), str(car.get("model", "")), car.get("year"))
        if key not in cache and len(cache) < limit:
            cache[key] = vpic.model_evidence(*key)
        row["vpic_evidence"] = cache.get(key, {
            "status": "not_checked", "verified": None,
            "reason": "vPIC lookup budget reserved for higher-ranked results",
        })
        enriched.append(row)
    return enriched


def evidence_context(cars: list[dict]) -> str:
    """Serialize only retrieved fields that the LLM is allowed to discuss."""
    blocks = []
    for car in cars[:5]:
        evidence = car.get("vpic_evidence", {})
        facts = [
            f"[car:{car.get('id')}]",
            f"vehicle={car.get('year')} {car.get('make')} {car.get('model')}",
            f"msrp={car.get('msrp')}", f"horsepower={car.get('engine_hp')}",
            f"fuel={car.get('engine_fuel_type')}",
            f"transmission={car.get('transmission_type')}",
            f"body_style={car.get('vehicle_style')}",
            f"city_mpg={car.get('city_mpg')}", f"highway_mpg={car.get('highway_mpg')}",
            f"vpic_status={evidence.get('status')}",
            f"vpic_vehicle_type={evidence.get('vehicle_type')}",
        ]
        blocks.append("; ".join(facts))
    return "\n".join(blocks)


def generate_grounded_summary(query: str, cars: list[dict]) -> tuple[str, str]:
    """Generate through LangChain + Ollama, falling back without losing results."""
    if not cars:
        return "No exact matches were found for the extracted constraints.", "deterministic"
    prompt = PROMPT.format(query=query, context=evidence_context(cars))
    try:
        response = get_chat_model(temperature=0).invoke(prompt)
        text = str(getattr(response, "content", response)).strip()
        allowed_ids = {str(car.get("id")) for car in cars[:5]}
        cited_ids = set(re.findall(r"\[car:([^\]]+)\]", text))
        if text and cited_ids and cited_ids.issubset(allowed_ids):
            return text, "langchain-ollama"
    except Exception:
        pass
    names = ", ".join(
        f"{car.get('year')} {car.get('make')} {car.get('model')} [car:{car.get('id')}]"
        for car in cars[:3]
    )
    return f"Ollama is unavailable; the top grounded Elasticsearch matches are {names}.", "deterministic"
