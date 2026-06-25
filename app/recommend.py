"""Lightweight recommendation scoring.

Given a set of customer preferences, rank catalog vehicles by how well they fit.
Each candidate gets a 0-100 score plus human-readable reasons, so the result can
be shown directly in the UI (and is RAG/LLM-ready, matching a.JSON's intent).
"""
from __future__ import annotations

from typing import Any


def _norm(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def score_vehicle(row: dict[str, Any], prefs: dict[str, Any]) -> tuple[float, list[str]]:
    """Return (score 0-100, reasons) for one vehicle against preferences."""
    score = 0.0
    weight = 0.0
    reasons: list[str] = []

    mode = prefs.get("mode", "buy")
    price = row["rent_daily"] if mode == "rent" else row["buy_price"]
    budget = prefs.get("budget_max")

    # Price fit (heavier weight) -------------------------------------------- #
    if budget:
        weight += 3
        if price <= budget:
            ratio = price / budget if budget else 1
            pts = 1.0 - 0.5 * ratio  # cheaper within budget scores higher
            score += 3 * pts
            label = f"${price:,}/day" if mode == "rent" else f"${price:,}"
            reasons.append(f"Within budget at {label}")
        else:
            reasons.append("Over budget")  # stays in list but penalised

    # Priorities ------------------------------------------------------------ #
    priorities = set(prefs.get("priorities", []))
    if "efficiency" in priorities:
        weight += 2
        eff = _norm(row.get("mpg_hwy") or 0, 15, 55)
        score += 2 * eff
        if (row.get("mpg_hwy") or 0) >= 35:
            reasons.append(f"Fuel-efficient ({row['mpg_hwy']} hwy MPG)")
    if "performance" in priorities:
        weight += 2
        perf = _norm(row.get("engine_hp") or 0, 100, 500)
        score += 2 * perf
        if (row.get("engine_hp") or 0) >= 300:
            reasons.append(f"High performance ({row['engine_hp']} HP)")
    if "price" in priorities:
        weight += 2
        # cheaper is better, normalised against a broad range
        cheap = 1.0 - _norm(price, 0, budget or (row["buy_price"] or 1))
        score += 2 * cheap

    # Seats ----------------------------------------------------------------- #
    min_seats = prefs.get("min_seats")
    if min_seats:
        weight += 1
        if (row.get("seats") or 0) >= min_seats:
            score += 1
            reasons.append(f"Seats {row['seats']}")
        else:
            reasons.append(f"Only {row.get('seats')} seats")

    # Popularity tiebreaker ------------------------------------------------- #
    weight += 0.5
    score += 0.5 * _norm(row.get("popularity") or 0, 0, 5000)

    final = round(100 * score / weight, 1) if weight else 0.0
    return final, reasons
