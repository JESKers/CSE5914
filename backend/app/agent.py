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
import re
import uuid
from datetime import date, datetime
from typing import Any, Callable

import requests

from search import search_service, vpic

from . import images, store, synth
from .config import settings
from .schemas import SearchFilters

MAX_AGENT_ITERATIONS = 12   # hard cap on model<->tool round trips per user turn
MAX_RESULTS_TO_MODEL = 8    # keep tool payloads small so context stays lean
MAX_RENTAL_UNITS = 10       # rental comparisons benefit from a few more options
MAX_OLLAMA_HISTORY_MESSAGES = 24
DEFAULT_SHOP_RESULTS_TO_SHOW = 12
MAX_SHOP_RESULTS_TO_SHOW = 20
MAX_SHOP_DIVERSITY_CANDIDATES = 200

# Adaptive thinking is only accepted on Claude 4.6+ / Sonnet 5 / Fable models;
# older ones (e.g. Haiku 4.5) reject the parameter with a 400, so gate it.
_ADAPTIVE_THINKING_PREFIXES = (
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
    "claude-sonnet-4-6", "claude-sonnet-5", "claude-fable", "claude-mythos",
)


def _supports_adaptive_thinking(model: str) -> bool:
    return model.startswith(_ADAPTIVE_THINKING_PREFIXES)

_SESSIONS: dict[str, list[dict[str, Any]]] = {}
_OLLAMA_SESSIONS: dict[str, list[dict[str, Any]]] = {}
_OLLAMA_SHOP_FILTERS: dict[str, SearchFilters] = {}
_OLLAMA_SHOP_PAGES: dict[str, int] = {}
_OLLAMA_SHOP_COUNTS: dict[str, int] = {}


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
    """Resolve a branch id leniently (case-insensitive, city-name fallback)."""
    locs = synth.rental_locations()
    wanted = str(location_id or "").strip().upper()
    loc = next((l for l in locs if l["id"].upper() == wanted), None)
    if loc is None:  # tolerate a city name / guessed id; cheapest branch wins
        by_city = [l for l in locs if l["city"].upper() in wanted or wanted in l["city"].upper()]
        loc = min(by_city, key=lambda l: l["daily_rate_multiplier"]) if by_city else None
    if loc is None:
        valid = ", ".join(l["id"] for l in locs)
        raise ValueError(f"Unknown rental location '{location_id}'. Valid ids: {valid}")
    return loc


def _with_image(payload: dict[str, Any], make: Any, model: Any) -> dict[str, Any]:
    url = images.image_for(make and str(make), model and str(model))
    if url:
        payload["image_url"] = url
    return payload


# --------------------------------------------------------------------------- #
# Tool implementations — each returns (payload, one-line summary for the UI)
# --------------------------------------------------------------------------- #
def _t_search_cars(args: dict[str, Any]) -> tuple[Any, str]:
    args = {k: v for k, v in args.items() if v not in (None, "")}
    args["size"] = min(int(args.get("size", MAX_RESULTS_TO_MODEL)), MAX_RESULTS_TO_MODEL)
    filters = SearchFilters(**args)
    res = search_service.search(filters)
    results = [_with_image(_compact_car(c), c.get("make"), c.get("model"))
               for c in res["results"]]
    payload = {"total": res["total"], "results": results}
    return payload, f"Searched catalog: {res['total']} matches"


def _t_get_listing(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    try:
        verified = vpic.is_verified(str(car.get("make", "")))
    except Exception:
        verified = False
    sold = store.purchases_by_vehicle().get(str(args["vehicle_id"]), 0)
    listing = store.to_listing(car, verified=verified, sold=sold)
    _with_image(listing, car.get("make"), car.get("model"))
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
    top = [_with_image(dict(u), u.get("make"), u.get("model"))
           for u in matches[:MAX_RENTAL_UNITS]]
    payload = {"location": loc, "days": days, "count": len(matches), "units": top}
    return payload, f"Found {len(matches)} available cars at {loc['name']}"


def _t_get_rental_addons(_args: dict[str, Any]) -> tuple[Any, str]:
    catalog = synth._table("rental_addons")
    return catalog, "Loaded add-on & protection catalog"


def _t_quote_rental(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    loc = _location(args["location_id"])
    days = _rental_days(args["pickup"], args["dropoff"])
    quote = synth.quote_rental(
        car, loc["id"], days=days,
        addons=args.get("addons") or {}, protection=args.get("protection") or [],
        driver_age=int(args.get("driver_age") or 30),
    )
    label = f"{car.get('year')} {car.get('make')} {car.get('model')}"
    return quote, f"Quoted {label}: ${quote['total']:,.2f} for {days} day(s)"


def _t_book_rental(args: dict[str, Any]) -> tuple[Any, str]:
    car = _get_car(args["vehicle_id"])
    loc = _location(args["location_id"])
    days = _rental_days(args["pickup"], args["dropoff"])
    unit_id = f"{loc['id']}-{car['id']}"
    if not synth.is_available(unit_id, args["pickup"], args["dropoff"]):
        raise ValueError("That vehicle is no longer available for those dates")
    quote = synth.quote_rental(
        car, loc["id"], days=days,
        addons=args.get("addons") or {}, protection=args.get("protection") or [],
        driver_age=int(args.get("driver_age") or 30),
    )
    booking = synth.book_rental(
        car, loc["id"], pickup=args["pickup"], dropoff=args["dropoff"],
        days=days, total=quote["total"], addons=args.get("addons") or {},
        protection=args.get("protection") or [], customer=args.get("customer"),
    )
    booking.update(synth.unit_identity(loc["id"], str(car["id"])))
    booking["pickup_location"] = loc
    _with_image(booking, car.get("make"), car.get("model"))
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
        "description": "List rental branches: exact `id` (use it verbatim in later calls), name, street address, phone, opening hours, rate multiplier. Call first in any rental flow to resolve the pickup city to a location_id.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_rental_inventory",
        "description": "Search available rental cars at one branch for a date range. Filters: minimum seats, max daily rate (USD), rental class (Economy/Standard/SUV/Truck/Luxury/Sport). Returns available units sorted by daily rate, each with license plate, color, odometer, seats, per-day rate, estimated base total and (when found) a photo image_url. Call this to find and compare rental options.",
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
1. Resolve relative dates against today's date. Resolve the city to a branch with list_rental_locations and use the branch's exact `id` in later calls (prefer the cheaper non-airport branch unless they need the airport).
2. search_rental_inventory with their seat/budget/class constraints; compare the top options on price and fit.
3. Add requested extras from get_rental_addons; recommend the sensible protection (CDW at minimum) and include it unless the user declined insurance.
4. quote_rental to verify the all-in total respects their budget (their per-day budget refers to the base daily rate unless they say all-in).
5. book_rental and present the confirmation.
Complete the whole chain in one go without asking for permission between steps. Only stop to ask if a hard requirement is impossible (e.g. nothing fits the budget) — then present the closest alternatives and ask which to book.
Present the rental result like a real reservation, in two parts:
- A short comparison table of the 2-4 best units you considered (plate, class, seats, color, $/day, est. total) with a one-line reason for your pick.
- The confirmation: confirmation number, vehicle (year make model + plate + color + odometer), pickup/dropoff dates, branch name + street address + phone + hours, itemized costs (base, each add-on, protection, fees, tax, total). Include the car photo if image_url is available.

BUY — decision support, then offline handoff. When a user is shopping to own:
1. Understand needs, search_cars to shortlist 2-3 candidates, and get_listing for prices/stock.
2. Use compare_tco (and quote_loan / quote_lease for specifics) to compare leasing vs buying new vs CPO over their ownership window — surface monthly payment, total interest, depreciation and net cost, and give a clear recommendation with reasons.
3. When they like a car, get_dealer_and_slots and offer to book_test_drive; after booking, hand off the dealer's name, phone and email so they can negotiate and close offline.
4. Never place_purchase_order unless the user explicitly asks to buy now.

Formatting: your replies render as GitHub-flavored markdown. Use compact GFM tables for any comparison (keep them to <=6 columns so they fit a chat panel), **bold** only for the few numbers that matter, and short paragraphs — no walls of text. When a tool result carries an image_url for the car you are recommending or booking, embed it with ![year make model](image_url); at most 2 images per reply.

Honesty rules (hard requirements):
- Never say a booking, order or appointment is confirmed unless a book_rental / book_test_drive / place_purchase_order tool call SUCCEEDED in this conversation. Confirmation numbers, plates, addresses and prices must be copied verbatim from tool results — never invent or round them.
- If you only quoted but did not book, say so explicitly and either book it or ask.
- If a tool errors, say what failed and offer the nearest alternative.

Style: reply in the user's language (they may write Chinese — answer in Chinese then). Be concrete and keep replies compact."""


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
    _OLLAMA_SESSIONS.pop(session_id, None)
    _OLLAMA_SHOP_FILTERS.pop(session_id, None)
    _OLLAMA_SHOP_PAGES.pop(session_id, None)
    _OLLAMA_SHOP_COUNTS.pop(session_id, None)


def _chat_anthropic(session_id: str, user_message: str) -> dict[str, Any]:
    """Run one turn through Claude's native tool-use API."""
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


def _ollama_mode(history: list[dict[str, Any]]) -> str:
    """Choose a compact local toolset from the conversation's user messages."""
    user_messages = [
        str(message.get("content") or "").casefold()
        for message in history
        if message.get("role") == "user"
    ]

    def classify(text: str) -> str | None:
        if any(word in text for word in (
            "rent", "rental", "pickup", "dropoff", "per day", "/day",
        )):
            return "rental"
        if any(word in text for word in (
            "buy", "purchase", "lease", "loan", "finance", "financing",
            "test drive", "dealer", "tco",
        )):
            return "buy"
        if any(word in text for word in (
            "car", "vehicle", "suv", "sedan", "coupe", "truck", "wagon",
            "hatchback", "minivan", "convertible",
        )):
            return "shop"
        return None

    # The newest explicit intent wins, allowing "actually, I want to buy" to
    # switch away from a rental flow. Ambiguous follow-ups inherit prior mode.
    if user_messages:
        latest_mode = classify(user_messages[-1])
        if latest_mode:
            return latest_mode
    for text in reversed(user_messages[:-1]):
        previous_mode = classify(text)
        if previous_mode:
            return previous_mode
    return "general"


def _ollama_tools(mode: str) -> list[dict[str, Any]]:
    """Translate only the mode-relevant tools to Ollama's function format."""
    names_by_mode = {
        "rental": {
            "list_rental_locations", "search_rental_inventory",
            "get_rental_addons", "quote_rental", "book_rental",
        },
        "buy": {
            "search_cars", "get_listing", "quote_loan", "quote_lease",
            "compare_tco", "get_dealer_and_slots", "book_test_drive",
            "place_purchase_order",
        },
        "shop": {"search_cars", "get_listing"},
        "general": set(),
    }
    allowed = names_by_mode[mode]
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in TOOLS
        if tool["name"] in allowed
    ]


def _ollama_system_prompt(mode: str) -> str:
    if mode == "general":
        return (
            "You are the JESKers car concierge. Answer naturally and briefly. "
            "Explain that you can search cars, compare buying and leasing, quote "
            "rentals, and help book rentals or test drives. Do not output JSON or "
            "invent tool calls. Reply in the user's language."
        )
    common = (
        f"You are the JESKers car concierge. Today is {date.today().isoformat()}. "
        "Use only supplied tools and treat their results as authoritative. Never "
        "invent vehicles, prices, availability, addresses, plates, appointments, "
        "orders, or confirmation numbers. Never write a function call as plain "
        "JSON. Use compact Markdown and reply in the user's language. "
    )
    if mode == "rental":
        return common + (
            "For rentals, collect or infer the city, pickup date, dropoff date, "
            "seat count, class, and daily budget. Ask one concise question when "
            "required dates or location are missing. Otherwise list locations, "
            "search live inventory, compare suitable units, load requested add-ons, "
            "and quote the best fit. Book only when the user clearly asks to reserve "
            "or confirms the choice. A rental is confirmed only after book_rental "
            "succeeds; copy every booking fact exactly from that result."
        )
    return common + (
        "For buying or leasing, search the catalog before recommending a vehicle. "
        "Use listing, loan, lease, and TCO tools for factual comparisons. Explain "
        "the tradeoff in plain language. Book a test drive only when requested, and "
        "place a purchase order only after an explicit request to buy now. An action "
        "is confirmed only after its booking or order tool succeeds."
    )


def _is_shop_followup(message: str) -> bool:
    """Recognize refinements that should inherit prior search constraints."""
    return bool(re.search(
        r"\b(?:cheaper|newer|older|faster|those|them|ones|instead|"
        r"only|also|same|more|less|next|previous|back|remove|clear|"
        r"forget|ignore|without|what about|how about)\b",
        message.casefold(),
    ))


def _shop_page_delta(message: str) -> int:
    normalized = message.casefold()
    if re.search(
        r"\b(?:previous|prior|back)(?:\s+(?:page|results?|options?|cars?))?\b",
        normalized,
    ):
        return -1
    if re.search(
        r"\b(?:next\s+(?:page|results?|options?|cars?)|"
        r"more\s+(?:results?|options?|cars?))\b",
        normalized,
    ):
        return 1
    return 0


def _shop_filter_removals(message: str) -> tuple[set[str], list[str], bool]:
    """Translate natural-language reset commands into fields to clear."""
    normalized = message.casefold()
    if re.search(
        r"\b(?:start over|reset(?:\s+all)?(?:\s+filters?)?|"
        r"clear all|forget everything|new search)\b",
        normalized,
    ):
        return set(), ["all filters"], True

    groups = (
        (
            r"\b(?:remove|clear|forget|ignore|drop|no)\b.{0,25}"
            r"\b(?:price|budget|cost|price limit)\b|"
            r"\b(?:any price|no budget|without a budget)\b",
            {"price_min", "price_max", "preferred_price_max"},
            "budget",
        ),
        (
            r"\b(?:remove|clear|forget|ignore|drop)\b.{0,25}"
            r"\b(?:make|brand)\b|\b(?:any make|any brand|brand does not matter)\b",
            {"make", "makes", "preferred_makes", "excluded_makes"},
            "make",
        ),
        (
            r"\b(?:remove|clear|forget|ignore|drop)\b.{0,25}\bmodel\b|"
            r"\bany model\b",
            {"model", "models", "excluded_models"},
            "model",
        ),
        (
            r"\b(?:remove|clear|forget|ignore|drop)\b.{0,25}"
            r"\b(?:year|age|newer|older)\b|\b(?:any year|any age)\b",
            {"year_min", "year_max", "preferred_year_min"},
            "year",
        ),
        (
            r"\b(?:remove|clear|forget|ignore|drop)\b.{0,25}"
            r"\b(?:style|body|suv|sedan|coupe|truck|wagon|hatchback|minivan)\b|"
            r"\b(?:any style|any body style)\b",
            {
                "vehicle_styles", "preferred_vehicle_styles",
                "excluded_vehicle_styles",
            },
            "body style",
        ),
        (
            r"\b(?:remove|clear|forget|ignore|drop)\b.{0,25}"
            r"\b(?:fuel|powertrain|hybrid|electric|diesel|gasoline)\b|"
            r"\b(?:any fuel|any powertrain)\b",
            {
                "engine_fuel_type", "powertrains", "preferred_powertrains",
                "excluded_powertrains",
            },
            "powertrain",
        ),
        (
            r"\b(?:remove|clear|forget|ignore|drop)\b.{0,25}"
            r"\b(?:transmission|automatic|manual)\b|\bany transmission\b",
            {
                "transmission_type", "transmission_types",
                "excluded_transmission_types",
            },
            "transmission",
        ),
        (
            r"\b(?:remove|clear|forget|ignore|drop)\b.{0,25}"
            r"\b(?:drivetrain|awd|4wd|fwd|rwd)\b|\bany drivetrain\b",
            {
                "driven_wheels", "preferred_driven_wheels",
                "excluded_driven_wheels",
            },
            "drivetrain",
        ),
    )
    fields: set[str] = set()
    labels: list[str] = []
    for pattern, group_fields, label in groups:
        if re.search(pattern, normalized):
            fields.update(group_fields)
            labels.append(label)
    return fields, labels, False


def _merge_shop_filters(
    previous: SearchFilters | None,
    current: SearchFilters,
    *,
    followup: bool,
    remove_fields: set[str] | None = None,
    reset_all: bool = False,
) -> SearchFilters:
    if reset_all:
        return SearchFilters()
    if previous is None or not followup:
        return current

    merged = previous.model_dump(exclude_none=True)
    current_data = current.model_dump(exclude_none=True)
    explicit = current.model_fields_set

    replacement_groups = (
        {"make", "makes"},
        {"model", "models"},
        {"transmission_type", "transmission_types"},
        {"vehicle_styles", "preferred_vehicle_styles"},
        {"vehicle_sizes", "preferred_vehicle_sizes"},
        {"driven_wheels", "preferred_driven_wheels"},
        {"market_categories", "preferred_market_categories"},
        {"powertrains", "preferred_powertrains"},
    )
    for group in replacement_groups:
        if group & explicit:
            for key in group:
                merged.pop(key, None)

    for key in explicit:
        if key == "q":
            # Comparative follow-ups such as "cheaper ones" are control
            # language, not catalog keywords. Keep any earlier real keyword.
            continue
        if key in current_data:
            merged[key] = current_data[key]
    for key in remove_fields or set():
        merged.pop(key, None)
    if {"price_min", "price_max", "preferred_price_max"} & (remove_fields or set()):
        remaining = [
            item for item in merged.get("ranking_preferences", [])
            if item != "affordability"
        ]
        if remaining:
            merged["ranking_preferences"] = remaining
        else:
            merged.pop("ranking_preferences", None)
    merged["page"] = 1
    return SearchFilters(**merged)


def _filter_interpretation(filters: SearchFilters) -> str:
    """Render the important parsed constraints in plain language."""
    details: list[str] = []
    makes = filters.makes or ([filters.make] if filters.make else [])
    models = filters.models or ([filters.model] if filters.model else [])
    if makes:
        details.append("make: " + " or ".join(makes))
    if models:
        details.append("model: " + " or ".join(models))
    if filters.vehicle_styles:
        details.append("style: " + " or ".join(filters.vehicle_styles))
    if filters.year_min is not None and filters.year_max is not None:
        details.append(
            f"year: {filters.year_min}"
            if filters.year_min == filters.year_max
            else f"years: {filters.year_min}-{filters.year_max}"
        )
    elif filters.year_min is not None:
        details.append(f"year: {filters.year_min} or newer")
    elif filters.year_max is not None:
        details.append(f"year: {filters.year_max} or older")
    if filters.price_max is not None:
        details.append(f"budget: up to ${filters.price_max:,.0f}")
    if filters.price_min is not None:
        details.append(f"minimum price: ${filters.price_min:,.0f}")

    preference_labels = {
        "affordability": "affordability",
        "fuel_economy": "fuel economy",
        "performance": "performance",
        "newer": "newer models",
        "family_space": "family space",
        "cargo_space": "cargo space",
        "all_weather": "all-weather capability",
        "city_driving": "city driving",
        "highway_driving": "highway driving",
    }
    preferences = [
        preference_labels[p]
        for p in filters.ranking_preferences or []
        if p in preference_labels
    ]
    if preferences:
        details.append("priorities: " + ", ".join(preferences))
    if filters.sort != "popularity":
        details.append(f"sorted by {filters.sort.replace('_', ' ')} {filters.order}")
    return "; ".join(details) or "a broad catalog search"


def _requested_shop_result_count(message: str, previous: int | None = None) -> int:
    """Choose a readable result count while honoring explicit user requests."""
    normalized = message.casefold()
    patterns = (
        r"\b(?:show|list|give|display|see)(?:\s+me)?\s+(?:the\s+top\s+)?(\d{1,2})\b",
        r"\b(?:top\s+)?(\d{1,2})\s+(?:cars?|vehicles?|options?|results?)\b",
    )
    for pattern in patterns:
        if match := re.search(pattern, normalized):
            return max(1, min(int(match.group(1)), MAX_SHOP_RESULTS_TO_SHOW))
    if (
        not _shop_page_delta(message)
        and re.search(r"\b(?:show|see|list|give|want).*\b(?:more|all)\b", normalized)
    ):
        return MAX_SHOP_RESULTS_TO_SHOW
    return previous or DEFAULT_SHOP_RESULTS_TO_SHOW


def _diversify_cars(cars: list[dict[str, Any]], *, include_all_trims: bool) -> list[dict[str, Any]]:
    """Keep the best-ranked representative of each model unless trims are requested."""
    if include_all_trims:
        return cars
    diversified = []
    seen = set()
    for car in cars:
        key = (
            str(car.get("make") or "").casefold(),
            str(car.get("model") or "").casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        diversified.append(car)
    return diversified


def _car_match_reasons(car: dict[str, Any], filters: SearchFilters) -> list[str]:
    """Build short explanations using only facts present in the search hit."""
    reasons: list[str] = []
    price = car.get("msrp")
    combined = car.get("combined_mpg")
    if combined is None and car.get("city_mpg") is not None and car.get("highway_mpg") is not None:
        combined = round((car["city_mpg"] + car["highway_mpg"]) / 2)

    preferences = set(filters.ranking_preferences or [])
    if filters.sort == "price" and price is not None:
        reasons.append(f"low price ${float(price):,.0f}")
    elif filters.price_max is not None and price is not None:
        room = filters.price_max - float(price)
        if room >= 0:
            reasons.append(f"${room:,.0f} under budget")
    if (
        filters.sort == "combined_mpg"
        or "fuel_economy" in preferences
        or filters.preferred_combined_mpg_min is not None
    ) and combined is not None:
        reasons.append(f"{combined} combined MPG")
    if (
        filters.sort == "hp"
        or "performance" in preferences
        or filters.hp_min is not None
    ) and car.get("engine_hp") is not None:
        reasons.append(f"{car['engine_hp']} hp")
    if filters.sort == "year" or "newer" in preferences:
        reasons.append(f"{car.get('year')} model")
    if "all_weather" in preferences and car.get("driven_wheels"):
        reasons.append(str(car["driven_wheels"]))
    if "family_space" in preferences and car.get("vehicle_style"):
        reasons.append(str(car["vehicle_style"]))
    return reasons[:2] or ["matches requested filters"]


def _catalog_context_note(
    user_message: str,
    filters: SearchFilters,
    minimum_year: int,
    maximum_year: int,
) -> str:
    normalized = user_message.casefold()
    relative = re.search(
        r"\b(?:last|past)\s+\w+\s+(?:model\s+)?years?\b|"
        r"\b\d+\s+years?\s+old\b|\bnewest\b|\blatest\b",
        normalized,
    )
    if filters.year_min is not None and filters.year_min > maximum_year:
        return (
            f"The catalog covers model years {minimum_year}-{maximum_year}, "
            f"but this request requires {filters.year_min} or newer."
        )
    if relative:
        return (
            f"Relative year language is evaluated against the catalog's "
            f"{minimum_year}-{maximum_year} coverage."
        )
    return ""


def _grounded_shop_reply(
    user_message: str,
    session_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Answer direct shopping searches from parsed Elasticsearch evidence."""
    from rag.parser import _catalog_year_bounds, parse_query

    current = parse_query(user_message)
    previous = _OLLAMA_SHOP_FILTERS.get(session_id) if session_id else None
    remove_fields, removed_labels, reset_all = _shop_filter_removals(user_message)
    page_delta = _shop_page_delta(user_message)
    followup = _is_shop_followup(user_message) or bool(
        previous and (remove_fields or reset_all or page_delta)
    )
    filters = _merge_shop_filters(
        previous,
        current,
        followup=followup,
        remove_fields=remove_fields,
        reset_all=reset_all,
    )

    previous_count = _OLLAMA_SHOP_COUNTS.get(session_id) if session_id else None
    requested_count = _requested_shop_result_count(user_message, previous_count)
    previous_page = _OLLAMA_SHOP_PAGES.get(session_id, 1) if session_id else 1
    page = max(1, previous_page + page_delta) if page_delta else 1
    if session_id:
        _OLLAMA_SHOP_FILTERS[session_id] = filters
        _OLLAMA_SHOP_COUNTS[session_id] = requested_count

    candidate_filters = filters.model_copy(update={
        "page": 1,
        "size": MAX_SHOP_DIVERSITY_CANDIDATES,
    })
    result = search_service.search(candidate_filters)
    result["query_echo"] = filters.model_dump(exclude_none=True)
    understood = _filter_interpretation(filters)
    all_trims = bool(re.search(r"\b(?:all|every)\s+trims?\b", user_message.casefold()))
    candidates = _diversify_cars(result["results"], include_all_trims=all_trims)
    total_pages = max(1, (len(candidates) + requested_count - 1) // requested_count)
    page = min(page, total_pages)
    if session_id:
        _OLLAMA_SHOP_PAGES[session_id] = page
    offset = (page - 1) * requested_count
    cars = candidates[offset:offset + requested_count]
    result.update(
        displayed_results=cars,
        display_page=page,
        display_size=requested_count,
        diverse_total=len(candidates),
    )
    minimum_year, maximum_year = _catalog_year_bounds()
    catalog_note = _catalog_context_note(
        user_message,
        filters,
        minimum_year,
        maximum_year,
    )
    if not result["results"]:
        detail = f"\n\nCatalog note: {catalog_note}" if catalog_note else ""
        return (
            f"**I understood:** {understood}.\n\n"
            "I couldn't find an exact catalog match for those requirements. "
            "Try increasing the budget, widening the year range, or changing "
            f"the body style.{detail}",
            result,
        )

    lines = [
        "| Vehicle | MSRP | MPG (city/highway) | Transmission | Why it matches |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for car in cars:
        price = car.get("msrp")
        price_text = f"${float(price):,.0f}" if price is not None else "N/A"
        city = car.get("city_mpg")
        highway = car.get("highway_mpg")
        mpg_text = f"{city or 'N/A'} / {highway or 'N/A'}"
        vehicle = f"{car.get('year')} {car.get('make')} {car.get('model')}"
        reasons = "; ".join(_car_match_reasons(car, filters)).replace("|", "/")
        lines.append(
            f"| {vehicle} | {price_text} | {mpg_text} | "
            f"{car.get('transmission_type') or 'N/A'} | {reasons} |"
        )
    update = (
        f"**Updated:** removed {', '.join(removed_labels)}.\n\n"
        if removed_labels else ""
    )
    result_kind = "options" if all_trims else "different models"
    intro = (
        f"{update}**I understood:** {understood}.\n\n"
        f"I found **{result['total']}** matching vehicles. "
        f"Showing page **{page} of {total_pages}** with **{len(cars)}** "
        f"{result_kind}:"
    )
    warnings = filters.unsupported_preferences or []
    notes = []
    if warnings:
        notes.append("I cannot verify " + ", ".join(warnings) + ".")
    if catalog_note:
        notes.append(catalog_note)
    note_text = "\n\nCatalog note: " + " ".join(notes) if notes else ""
    return "\n".join([intro, "", *lines]) + note_text, result


def _trim_ollama_history(history: list[dict[str, Any]]) -> None:
    """Bound local context growth while keeping complete recent turns."""
    if len(history) <= MAX_OLLAMA_HISTORY_MESSAGES:
        return
    history[:] = history[-MAX_OLLAMA_HISTORY_MESSAGES:]
    while history and history[0].get("role") == "tool":
        history.pop(0)


def _chat_ollama(session_id: str, user_message: str) -> dict[str, Any]:
    """Run one turn through local Ollama while preserving the agent tools."""
    history = _OLLAMA_SESSIONS.setdefault(session_id, [])
    history.append({"role": "user", "content": user_message})
    events: list[dict[str, Any]] = []
    reply = ""
    base_url = settings.ollama_base_url.rstrip("/")
    mode = _ollama_mode(history)
    tools = _ollama_tools(mode)

    if mode == "shop":
        reply, result = _grounded_shop_reply(user_message, session_id)
        history.append({"role": "assistant", "content": reply})
        _trim_ollama_history(history)
        return {
            "reply": reply,
            "events": [{
                "tool": "search_cars",
                "summary": f"Searched catalog: {result['total']} matches",
                "is_error": False,
            }],
        }

    for _ in range(MAX_AGENT_ITERATIONS):
        payload: dict[str, Any] = {
            "model": settings.ollama_chat_model or "qwen3.5:4b",
            "messages": [
                {"role": "system", "content": _ollama_system_prompt(mode)},
                *history,
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }
        if tools:
            payload["tools"] = tools
        response = requests.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        message = response.json().get("message") or {}
        assistant_message = {
            "role": "assistant",
            "content": str(message.get("content") or ""),
        }
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            assistant_message["tool_calls"] = tool_calls
        history.append(assistant_message)

        if not tool_calls:
            reply = assistant_message["content"].strip()
            break

        for call in tool_calls:
            function = call.get("function") or {}
            name = str(function.get("name") or "")
            args = function.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            result_json, summary, is_error = _run_tool(name, dict(args))
            events.append({"tool": name, "summary": summary, "is_error": is_error})
            history.append({
                "role": "tool",
                "tool_name": name,
                "content": result_json,
            })

    if not reply:
        reply = "I ran out of steps before finishing — could you rephrase or narrow the request?"
    _trim_ollama_history(history)
    return {"reply": reply, "events": events}


def chat(session_id: str, user_message: str) -> dict[str, Any]:
    """Run one agent turn, preferring Claude and falling back to local Ollama."""
    if settings.anthropic_api_key:
        return _chat_anthropic(session_id, user_message)
    return _chat_ollama(session_id, user_message)
