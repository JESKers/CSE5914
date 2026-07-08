"""Conversational buy/rent assistant — an agentic tool-use loop over the store.

Two journeys, driven by one Claude agent with function tools:

  * RENT  — fully autonomous, end to end. "7-seater with a child seat in
    Columbus next Wed–Sun under $60/day" -> the agent searches branch
    inventory, compares rates, adds add-ons/protection, books, and returns a
    confirmation number without human intervention.
  * BUY   — decision support + offline handoff. The agent researches models,
    compares loan vs lease vs CPO total cost of ownership (synth.compare_tco),
    schedules a test drive, and hands off to a dealer contact.

The tools wrap the existing layers only: search_service (ES catalog),
store.py (listings/orders) and synth.py (finance/TCO, rental fleet, dealers).
Conversations are held in-memory per session_id — good enough for the demo;
the API itself stays stateless per the frozen contract (all /assistant/*
endpoints are additive).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import Any, Callable

from search import search_service, vpic

from . import store, synth
from .config import settings
from .schemas import SearchFilters

MAX_AGENT_ITERATIONS = 12   # hard cap on model<->tool round trips per user turn
MAX_RESULTS_TO_MODEL = 8    # keep tool payloads small so context stays lean

# Adaptive thinking is only accepted on Claude 4.6+ / Sonnet 5 / Fable models;
# older ones (e.g. Haiku 4.5) reject the parameter with a 400, so gate it.
_ADAPTIVE_THINKING_PREFIXES = (
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
    "claude-sonnet-4-6", "claude-sonnet-5", "claude-fable", "claude-mythos",
)


def _supports_adaptive_thinking(model: str) -> bool:
    return model.startswith(_ADAPTIVE_THINKING_PREFIXES)

_SESSIONS: dict[str, list[dict[str, Any]]] = {}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _compact_car(car: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "make", "model", "year", "msrp", "engine_hp",
            "engine_fuel_type", "transmission_type", "vehicle_style",
            "highway_mpg", "city_mpg")
    return {k: car.get(k) for k in keep if car.get(k) is not None}


def _get_car(vehicle_id: str) -> dict[str, Any]:
    car = search_service.get_car(str(vehicle_id))
    if not car:
        raise ValueError(f"Vehicle {vehicle_id} not found in the catalog")
    return car


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def _rental_days(pickup: str, dropoff: str) -> int:
    days = (_parse_date(dropoff) - _parse_date(pickup)).days
    if days < 1:
        raise ValueError("dropoff must be after pickup (dates are YYYY-MM-DD)")
    return days


def _location(location_id: str) -> dict[str, Any]:
    loc = next((l for l in synth.rental_locations() if l["id"] == location_id), None)
    if not loc:
        raise ValueError(f"Unknown rental location '{location_id}'")
    return loc


# --------------------------------------------------------------------------- #
# Tool implementations — each returns (payload, one-line summary for the UI)
# --------------------------------------------------------------------------- #
def _t_search_cars(args: dict[str, Any]) -> tuple[Any, str]:
    args = {k: v for k, v in args.items() if v not in (None, "")}
    args["size"] = min(int(args.get("size", MAX_RESULTS_TO_MODEL)), MAX_RESULTS_TO_MODEL)
    filters = SearchFilters(**args)
    res = search_service.search(filters)
    payload = {"total": res["total"], "results": [_compact_car(c) for c in res["results"]]}
    return payload, f"Searched catalog: {res['total']} matches"


def _t_get_listing(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    try:
        verified = vpic.is_verified(str(car.get("make", "")))
    except Exception:
        verified = False
    sold = store.purchases_by_vehicle().get(str(args["vehicle_id"]), 0)
    listing = store.to_listing(car, verified=verified, sold=sold)
    label = f"{car.get('year')} {car.get('make')} {car.get('model')}"
    return listing, f"Fetched listing for {label}"


def _t_list_rental_locations(_args: dict[str, Any]) -> tuple[Any, str]:
    locs = synth.rental_locations()
    return {"locations": locs}, f"Listed {len(locs)} rental branches"


def _t_search_rental_inventory(args: dict[str, Any]) -> tuple[Any, str]:
    loc = _location(args["location_id"])
    days = _rental_days(args["pickup"], args["dropoff"])

    filters = SearchFilters(q=args.get("q") or None, size=100, sort="popularity", order="desc")
    catalog = search_service.search(filters)["results"]
    units = synth.build_rental_inventory(catalog, loc["id"])

    seats_min = args.get("seats_min")
    max_rate = args.get("max_daily_rate")
    rental_class = args.get("rental_class")
    matches = []
    for u in units:
        if seats_min and u["seats"] < int(seats_min):
            continue
        if max_rate and u["daily_rate"] > float(max_rate):
            continue
        if rental_class and u["rental_class"].lower() != str(rental_class).lower():
            continue
        if not synth.is_available(u["unit_id"], args["pickup"], args["dropoff"]):
            continue
        matches.append({**u, "days": days, "base_total": round(u["daily_rate"] * days, 2)})
    matches.sort(key=lambda u: u["daily_rate"])
    payload = {"location": loc, "days": days, "count": len(matches),
               "units": matches[:MAX_RESULTS_TO_MODEL]}
    return payload, f"Found {len(matches)} available cars at {loc['name']}"


def _t_get_rental_addons(_args: dict[str, Any]) -> tuple[Any, str]:
    catalog = synth._table("rental_addons")
    return catalog, "Loaded add-on & protection catalog"


def _t_quote_rental(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    days = _rental_days(args["pickup"], args["dropoff"])
    quote = synth.quote_rental(
        car, args["location_id"], days=days,
        addons=args.get("addons") or {}, protection=args.get("protection") or [],
        driver_age=int(args.get("driver_age") or 30),
    )
    label = f"{car.get('year')} {car.get('make')} {car.get('model')}"
    return quote, f"Quoted {label}: ${quote['total']:,.2f} for {days} day(s)"


def _t_book_rental(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    days = _rental_days(args["pickup"], args["dropoff"])
    unit_id = f"{args['location_id']}-{car['id']}"
    if not synth.is_available(unit_id, args["pickup"], args["dropoff"]):
        raise ValueError("That vehicle is no longer available for those dates")
    quote = synth.quote_rental(
        car, args["location_id"], days=days,
        addons=args.get("addons") or {}, protection=args.get("protection") or [],
        driver_age=int(args.get("driver_age") or 30),
    )
    booking = synth.book_rental(
        car, args["location_id"], pickup=args["pickup"], dropoff=args["dropoff"],
        days=days, total=quote["total"], addons=args.get("addons") or {},
        protection=args.get("protection") or [], customer=args.get("customer"),
    )
    return {**booking, "quote": quote}, f"Booked {booking['label']} — confirmation {booking['confirmation']}"


def _t_quote_loan(args: dict[str, Any]) -> tuple[Any, str]:
    price = args.get("price")
    if price is None:
        price = float(_get_car(args["vehicle_id"]).get("msrp") or 0)
    quote = synth.quote_loan(
        float(price),
        credit_score=args.get("credit_score"),
        condition=args.get("condition") or "new",
        term_months=int(args.get("term_months") or 60),
        down_payment=args.get("down_payment"),
        state=args.get("state") or "OH",
    )
    return quote, f"Loan quote: ${quote['monthly_payment']:,.0f}/mo at {quote['apr']}% APR"


def _t_quote_lease(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    quote = synth.quote_lease(
        car,
        credit_score=args.get("credit_score"),
        term_months=int(args.get("term_months") or 36),
        annual_miles=int(args.get("annual_miles") or 12000),
        down_payment=float(args.get("down_payment") or 0.0),
    )
    return quote, f"Lease quote: ${quote['monthly_payment']:,.0f}/mo for {quote['term_months']} months"


def _t_compare_tco(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    result = synth.compare_tco(
        car,
        years=int(args.get("years") or 5),
        credit_score=args.get("credit_score"),
        annual_miles=int(args.get("annual_miles") or 12000),
        state=args.get("state") or "OH",
    )
    return result, f"TCO compared for {result['vehicle']}: best is {result['recommended']}"


def _t_get_dealer_and_slots(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    dealer = synth.assign_dealer(car)
    slots = synth.test_drive_slots(car)
    return {"dealer": dealer, "test_drive_slots": slots}, f"Dealer {dealer['name']} with {len(slots)} open slots"


def _t_book_test_drive(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    dealer = synth.assign_dealer(car)
    appt = synth.book_test_drive(car, dealer, args["slot"], customer=args.get("customer"))
    return appt, f"Test drive booked at {dealer['name']} — {appt['confirmation']}"


def _t_place_purchase_order(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    sold = store.purchases_by_vehicle().get(str(args["vehicle_id"]), 0)
    listing = store.to_listing(car, verified=False, sold=sold)
    if listing["stock"] <= 0:
        raise ValueError("Out of stock for purchase")
    label = f"{car.get('year')} {car.get('make')} {car.get('model')}"
    order_id = store.record_order(
        vehicle_id=str(car["id"]), label=label, mode="buy",
        total=listing["buy_price"], customer=args.get("customer"),
    )
    payload = {"order_id": order_id, "vehicle": label, "total": listing["buy_price"],
               "status": "confirmed"}
    return payload, f"Purchase order #{order_id} placed for {label}"


# --------------------------------------------------------------------------- #
# Tool schemas (Claude function tools)
# --------------------------------------------------------------------------- #
def _num(desc: str) -> dict:
    return {"type": "number", "description": desc}


def _int(desc: str) -> dict:
    return {"type": "integer", "description": desc}


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_cars",
        "description": "Search the car catalog (Elasticsearch). Call this when the user wants to find or compare vehicle models for buying or leasing. Returns compact car specs incl. MSRP. Use `q` for fuzzy descriptors (sporty, luxury, SUV).",
        "input_schema": {"type": "object", "properties": {
            "make": _str("exact make, e.g. Toyota"), "model": _str("exact model"),
            "year_min": _int("min model year"), "year_max": _int("max model year"),
            "price_min": _num("min MSRP in USD"), "price_max": _num("max MSRP in USD"),
            "hp_min": _int("min horsepower"), "hp_max": _int("max horsepower"),
            "engine_fuel_type": _str("fuel type keyword, e.g. electric, diesel"),
            "transmission_type": _str("AUTOMATIC or MANUAL"),
            "q": _str("free-text keywords for style/segment"),
            "sort": _str("price | year | hp | popularity"), "order": _str("asc | desc"),
            "size": _int("max results (<=8)"),
        }},
    },
    {
        "name": "get_listing",
        "description": "Fetch one vehicle's store listing: buy_price, rent_daily, seats, stock, and whether the make is NHTSA-vPIC verified. Call before quoting or booking anything for that vehicle.",
        "input_schema": {"type": "object", "properties": {"vehicle_id": _str("catalog vehicle id")},
                          "required": ["vehicle_id"]},
    },
    {
        "name": "list_rental_locations",
        "description": "List rental branches (id, city, name, rate multiplier). Call first in any rental flow to resolve the pickup city to a location_id.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_rental_inventory",
        "description": "Search available rental cars at one branch for a date range. Filters: minimum seats, max daily rate (USD), rental class (Economy/Standard/SUV/Truck/Luxury/Sport). Returns available units sorted by daily rate. Call this to find and compare rental options.",
        "input_schema": {"type": "object", "properties": {
            "location_id": _str("branch id from list_rental_locations"),
            "pickup": _str("pickup date YYYY-MM-DD"), "dropoff": _str("dropoff date YYYY-MM-DD"),
            "seats_min": _int("minimum seats needed"), "max_daily_rate": _num("max base daily rate in USD"),
            "rental_class": _str("Economy | Standard | SUV | Truck | Luxury | Sport"),
            "q": _str("optional free-text filter, e.g. minivan"),
        }, "required": ["location_id", "pickup", "dropoff"]},
    },
    {
        "name": "get_rental_addons",
        "description": "Get the rental add-on catalog (child seat, GPS, additional driver, ...) and protection/insurance products (CDW, LDW, SLI, ...) with per-day prices. Call before adding extras or insurance to a rental quote.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "quote_rental",
        "description": "Full rental price breakdown for one vehicle at a branch: base rate, add-ons, protection, airport fee, tax, total. addons maps addon code -> quantity; protection is a list of protection codes.",
        "input_schema": {"type": "object", "properties": {
            "vehicle_id": _str("catalog vehicle id"), "location_id": _str("branch id"),
            "pickup": _str("YYYY-MM-DD"), "dropoff": _str("YYYY-MM-DD"),
            "addons": {"type": "object", "description": "addon code -> quantity, e.g. {\"child_seat\": 1}"},
            "protection": {"type": "array", "items": {"type": "string"}, "description": "protection codes, e.g. [\"cdw\"]"},
            "driver_age": _int("driver age (under-25 fee applies below 25)"),
        }, "required": ["vehicle_id", "location_id", "pickup", "dropoff"]},
    },
    {
        "name": "book_rental",
        "description": "Confirm the rental booking. Persists the reservation and returns a confirmation number. Call once the vehicle, dates, add-ons and protection are settled — this completes the rental journey.",
        "input_schema": {"type": "object", "properties": {
            "vehicle_id": _str("catalog vehicle id"), "location_id": _str("branch id"),
            "pickup": _str("YYYY-MM-DD"), "dropoff": _str("YYYY-MM-DD"),
            "addons": {"type": "object", "description": "addon code -> quantity"},
            "protection": {"type": "array", "items": {"type": "string"}},
            "driver_age": _int("driver age"), "customer": _str("customer name/email if given"),
        }, "required": ["vehicle_id", "location_id", "pickup", "dropoff"]},
    },
    {
        "name": "quote_loan",
        "description": "Financed-purchase quote: APR by credit tier, sales tax, fees, monthly payment, total interest. Pass vehicle_id to price at MSRP, or an explicit price (e.g. a negotiated or CPO price).",
        "input_schema": {"type": "object", "properties": {
            "vehicle_id": _str("catalog vehicle id (uses MSRP)"), "price": _num("explicit price in USD"),
            "credit_score": _int("FICO score if known"),
            "condition": _str("new | cpo | used"), "term_months": _int("36|48|60|72"),
            "down_payment": _num("down payment in USD"), "state": _str("US state code, default OH"),
        }},
    },
    {
        "name": "quote_lease",
        "description": "Lease quote for a vehicle: money factor by credit tier, residual value, monthly payment, due at signing, total lease cost.",
        "input_schema": {"type": "object", "properties": {
            "vehicle_id": _str("catalog vehicle id"), "credit_score": _int("FICO score if known"),
            "term_months": _int("24|36|48"), "annual_miles": _int("annual mileage allowance"),
            "down_payment": _num("cap cost reduction in USD"),
        }, "required": ["vehicle_id"]},
    },
    {
        "name": "compare_tco",
        "description": "Side-by-side N-year total cost of ownership for buy-new vs certified pre-owned (CPO) vs lease — includes loan interest, depreciation/resale, maintenance, insurance, fuel. The core decision tool for the buy journey.",
        "input_schema": {"type": "object", "properties": {
            "vehicle_id": _str("catalog vehicle id"), "years": _int("ownership window, default 5"),
            "credit_score": _int("FICO score if known"), "annual_miles": _int("default 12000"),
            "state": _str("US state code, default OH"),
        }, "required": ["vehicle_id"]},
    },
    {
        "name": "get_dealer_and_slots",
        "description": "Get the assigned dealer (name, phone, email, rating) and upcoming open test-drive slots for a vehicle. Call when the buyer is ready to see the car or needs the offline handoff contact.",
        "input_schema": {"type": "object", "properties": {"vehicle_id": _str("catalog vehicle id")},
                          "required": ["vehicle_id"]},
    },
    {
        "name": "book_test_drive",
        "description": "Book a test-drive appointment at the assigned dealer. `slot` must be one returned by get_dealer_and_slots. Returns a confirmation number.",
        "input_schema": {"type": "object", "properties": {
            "vehicle_id": _str("catalog vehicle id"), "slot": _str("slot string 'YYYY-MM-DD HH:MM'"),
            "customer": _str("customer name/email if given"),
        }, "required": ["vehicle_id", "slot"]},
    },
    {
        "name": "place_purchase_order",
        "description": "Place a confirmed purchase order at the listed buy price. Only call after the user has explicitly said they want to buy this exact vehicle now.",
        "input_schema": {"type": "object", "properties": {
            "vehicle_id": _str("catalog vehicle id"), "customer": _str("customer name/email if given"),
        }, "required": ["vehicle_id"]},
    },
]

_DISPATCH: dict[str, Callable[[dict[str, Any]], tuple[Any, str]]] = {
    "search_cars": _t_search_cars,
    "get_listing": _t_get_listing,
    "list_rental_locations": _t_list_rental_locations,
    "search_rental_inventory": _t_search_rental_inventory,
    "get_rental_addons": _t_get_rental_addons,
    "quote_rental": _t_quote_rental,
    "book_rental": _t_book_rental,
    "quote_loan": _t_quote_loan,
    "quote_lease": _t_quote_lease,
    "compare_tco": _t_compare_tco,
    "get_dealer_and_slots": _t_get_dealer_and_slots,
    "book_test_drive": _t_book_test_drive,
    "place_purchase_order": _t_place_purchase_order,
}


# --------------------------------------------------------------------------- #
# System prompt
# --------------------------------------------------------------------------- #
def _system_prompt() -> str:
    return f"""You are the JESKers car concierge — a buy/rent assistant embedded in a car marketplace. Today's date is {date.today().isoformat()}. All inventory, prices and dealer data are synthetic demo data; treat them as authoritative for this store and never invent vehicles, prices or confirmation numbers — everything you state must come from a tool result.

You handle two journeys:

RENTAL — fully autonomous, end to end. When a user wants to rent (e.g. "a 7-seater with a child seat in Columbus next Wed to Sun, under $60/day"):
1. Resolve relative dates against today's date. Resolve the city to a branch with list_rental_locations (prefer the cheaper non-airport branch unless they need the airport).
2. search_rental_inventory with their seat/budget/class constraints; compare the top options on price and fit.
3. Add requested extras from get_rental_addons; recommend the sensible protection (CDW at minimum) and include it unless the user declined insurance.
4. quote_rental to verify the all-in total respects their budget (their per-day budget refers to the base daily rate unless they say all-in).
5. book_rental and present the confirmation number, pickup details and full price breakdown.
Complete the whole chain in one go without asking for permission between steps. Only stop to ask if a hard requirement is impossible (e.g. nothing fits the budget) — then present the closest alternatives and ask which to book.

BUY — decision support, then offline handoff. When a user is shopping to own:
1. Understand needs, search_cars to shortlist 2-3 candidates, and get_listing for prices/stock.
2. Use compare_tco (and quote_loan / quote_lease for specifics) to compare leasing vs buying new vs CPO over their ownership window — surface monthly payment, total interest, depreciation and net cost, and give a clear recommendation with reasons.
3. When they like a car, get_dealer_and_slots and offer to book_test_drive; after booking, hand off the dealer's name, phone and email so they can negotiate and close offline.
4. Never place_purchase_order unless the user explicitly asks to buy now.

Style: reply in the user's language (they may write Chinese — answer in Chinese then). Be concrete: show real numbers from tools, small comparison tables when comparing options, and always surface confirmation numbers. Keep replies compact. If a tool errors, say what failed and offer the nearest alternative."""


# --------------------------------------------------------------------------- #
# Agentic loop
# --------------------------------------------------------------------------- #
def _run_tool(name: str, args: dict[str, Any]) -> tuple[str, str, bool]:
    """Execute one tool call. Returns (json_result, summary, is_error)."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"}), f"Unknown tool {name}", True
    try:
        payload, summary = fn(args or {})
        return json.dumps(payload, ensure_ascii=False, default=str), summary, False
    except Exception as exc:  # surface tool failures to the model, not as a 500
        return json.dumps({"error": str(exc)}), f"{name} failed: {exc}", True


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def reset_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def chat(session_id: str, user_message: str) -> dict[str, Any]:
    """One user turn: run the model<->tool loop to completion, return the reply."""
    from anthropic import Anthropic  # lazy import, mirrors rag/parser.py

    client = Anthropic(api_key=settings.anthropic_api_key)
    model = settings.anthropic_model or "claude-opus-4-8"  # empty env var -> default
    thinking = {"thinking": {"type": "adaptive"}} if _supports_adaptive_thinking(model) else {}
    history = _SESSIONS.setdefault(session_id, [])
    history.append({"role": "user", "content": user_message})

    events: list[dict[str, Any]] = []
    response = None
    for _ in range(MAX_AGENT_ITERATIONS):
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            system=_system_prompt(),
            tools=TOOLS,
            messages=history,
            **thinking,
        )
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            continue
        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result_json, summary, is_error = _run_tool(block.name, dict(block.input or {}))
            events.append({"tool": block.name, "summary": summary, "is_error": is_error})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_json,
                "is_error": is_error,
            })
        history.append({"role": "user", "content": tool_results})

    reply = "".join(b.text for b in (response.content if response else []) if b.type == "text")
    if not reply:
        reply = "I ran out of steps before finishing — could you rephrase or narrow the request?"
    return {"reply": reply, "events": events}
