"""
FastAPI backend for GoodFoods reservation system.
"""

import json
import re
import os
import uvicorn
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('goodfoods.api')

# WHY pathlib here: hardcoded 'data/bookings_list.json' breaks if you run
# the app from any directory other than project root. __file__ is always
# the absolute path of this file itself — so this works from anywhere.
BASE_DIR = Path(__file__).parent

try:
    with open(BASE_DIR / 'bookings_list.json', 'r') as f:
        order_management_table: List[Dict[str, Any]] = json.load(f)
    logger.info("Loaded bookings_list.json")
except FileNotFoundError:
    logger.error("bookings_list.json not found")
    order_management_table = []

try:
    with open(BASE_DIR / 'restaurant_list.json', 'r') as f:
        restaurant_information_table: List[Dict[str, Any]] = json.load(f)
    logger.info("Loaded restaurant_list.json")
except FileNotFoundError:
    logger.error("restaurant_list.json not found")
    restaurant_information_table = []

app = FastAPI()


class RestaurantQuery(BaseModel):
    location: Optional[str] = None
    cuisine: Optional[Union[str, List[str]]] = None
    operating_days: Optional[str] = None
    operating_hours: Optional[Dict[str, str]] = None
    restaurant_max_seating_capacity: Optional[int] = None
    max_booking_party_size: Optional[int] = None


class Reservation(BaseModel):
    restaurant_id: str
    orderer_name: str
    orderer_contact: str
    party_size: int
    reservation_date: str
    reservation_time: str


def search_restaurant_information(query: Dict[str, Any]) -> Dict:
    logger.info(f"Search query: {query}")
    query = {k: v for k, v in query.items() if v}

    if not query:
        return {
            "status": "empty query",
            "message": "No criteria provided. Here are top options.",
            "restaurants": restaurant_information_table[:10]
        }

    matches = []
    for restaurant in restaurant_information_table:
        match_count = 0
        matched_fields = {}

        for key, value in query.items():
            if key == "cuisine":
                cuisines = restaurant.get("cuisine", [])
                if isinstance(value, str):
                    hit = any(value.lower() in c.lower() for c in cuisines)
                else:
                    hit = any(c in cuisines for c in value)
                if hit:
                    match_count += 1
                    matched_fields[key] = True

            elif key == "location":
                loc = restaurant.get("location", {})
                if (str(value).lower() in loc.get("address", "").lower() or
                        str(value).lower() in loc.get("landmark", "").lower()):
                    match_count += 1
                    matched_fields[key] = True

            elif key == "operating_days":
                days = restaurant.get("operating_days", [])
                if any(str(value).lower() in d.lower() for d in days):
                    match_count += 1
                    matched_fields[key] = True

            elif key == "operating_hours":
                hours = restaurant.get("operating_hours", {})
                ok = True
                if "open" in value and hours.get("open") != value["open"]:
                    ok = False
                if "close" in value and hours.get("close") != value["close"]:
                    ok = False
                if ok:
                    match_count += 1
                    matched_fields[key] = True

            elif key in ["restaurant_max_seating_capacity", "max_booking_party_size"]:
                try:
                    if restaurant.get(key, 0) >= int(str(value).strip()):
                        match_count += 1
                        matched_fields[key] = True
                except (ValueError, TypeError):
                    pass

        if match_count > 0:
            matches.append({**restaurant, "match_count": match_count, "matched_fields": matched_fields})

    matches.sort(key=lambda x: x["match_count"], reverse=True)

    if not matches:
        return {
            "status": "no_matches",
            "message": "No matches found. Here are top options.",
            "restaurants": restaurant_information_table[:10]
        }

    return {
        "status": "matches_found",
        "message": f"Found {len(matches)} restaurants.",
        "restaurants": matches
    }


def detect_placeholder_values(order_info: Dict[str, Any]) -> Dict:
    placeholder_names = [
        "user", "your name", "name", "customer", "placeholder",
        "john doe", "jane doe", "[name]", "(name)", "guest"
    ]
    placeholder_contacts = [
        "contact", "your phone", "phone", "mobile", "123456789",
        "1234567890", "user contact", "customer phone"
    ]

    has_placeholders = False
    placeholder_fields = []

    name_val = str(order_info.get("orderer_name", "")).lower().strip()
    if any(p in name_val for p in placeholder_names):
        has_placeholders = True
        placeholder_fields.append("orderer_name")

    contact_val = str(order_info.get("orderer_contact", "")).strip()
    # WHY: strip +91, spaces, dashes before validating
    # Indian numbers can come as +91-98765-43210 or 98765 43210 — both valid
    cleaned = re.sub(r'^\+?91', '', contact_val).replace(' ', '').replace('-', '')
    if not cleaned.isdigit() or len(cleaned) != 10:
        has_placeholders = True
        placeholder_fields.append("orderer_contact")

    for field in ["reservation_date", "reservation_time"]:
        if field in order_info:
            val = str(order_info[field]).lower()
            if any(w in val for w in ["tomorrow", "tonight", "today", "next"]):
                has_placeholders = True
                placeholder_fields.append(field)

    return {"has_placeholders": has_placeholders, "placeholder_fields": placeholder_fields}


def review_information_before_order(order_info: Dict[str, Any]) -> Dict:
    required = ["restaurant_id", "orderer_name", "orderer_contact",
                "party_size", "reservation_date", "reservation_time"]
    missing = [f for f in required if f not in order_info or not order_info[f]]
    placeholder_check = detect_placeholder_values(order_info)

    if missing or placeholder_check["placeholder_fields"]:
        return {
            "status": "invalid",
            "missing_fields": missing,
            "placeholder_fields": placeholder_check["placeholder_fields"]
        }
    return {"status": "complete"}


def check_capacity(restaurant_id: str, party_size: int,
                   reservation_date: str, reservation_time: str,
                   debug: bool = False) -> Union[bool, Dict]:
    restaurant = next((r for r in restaurant_information_table
                       if r["restaurant_id"] == restaurant_id), None)
    if not restaurant:
        return False

    max_cap = restaurant["restaurant_max_seating_capacity"]
    current = sum(
        o["party_size"] for o in order_management_table
        if o["restaurant_id"] == restaurant_id
        and o["reservation_date"] == reservation_date
        and o["reservation_time"] == reservation_time
    )
    available = max_cap - current
    within = (current + party_size) <= max_cap

    if debug:
        return {
            "is_within_capacity": within,
            "restaurant_id": restaurant_id,
            "max_capacity": max_cap,
            "current_total": current,
            "requested_party_size": party_size,
            "available_capacity": available
        }
    return within


def make_new_order(order_info: dict, capacity_debug: bool = False) -> Dict[str, Any]:
    logger.info(f"Order request: {order_info}")

    review = review_information_before_order(order_info)
    if review["status"] == "invalid":
        return {
            "status": "error",
            "message": "Validation failed",
            "missing_fields": review.get("missing_fields", []),
            "placeholder_fields": review.get("placeholder_fields", [])
        }

    capacity = check_capacity(
        order_info["restaurant_id"], order_info["party_size"],
        order_info["reservation_date"], order_info["reservation_time"],
        debug=capacity_debug
    )

    if isinstance(capacity, dict) and not capacity["is_within_capacity"]:
        return {"status": "error", "message": "Capacity exceeded.", "capacity_details": capacity}
    if isinstance(capacity, bool) and not capacity:
        return {"status": "error", "message": "Capacity exceeded."}

    order_id = f"ord{len(order_management_table) + 1:03d}"
    new_order = {**order_info, "order_id": order_id, "status": "confirmed"}

    try:
        order_management_table.append(new_order)
        with open(BASE_DIR / 'bookings_list.json', 'w') as f:
            json.dump(order_management_table, f, indent=2)
        logger.info(f"Order confirmed: {order_id}")
    except Exception as e:
        logger.error(f"Error saving order: {e}")

    return {"status": "success", "message": "Reservation confirmed", "order": new_order}


def get_order_by_id(order_id: str) -> Optional[Dict]:
    return next((o for o in order_management_table if o.get("order_id") == order_id), None)


def cancel_order(order_id: str) -> Dict:
    order = get_order_by_id(order_id)
    if not order:
        return {"status": "error", "message": f"Order {order_id} not found."}
    order["status"] = "cancelled"
    try:
        with open(BASE_DIR / 'bookings_list.json', 'w') as f:
            json.dump(order_management_table, f, indent=2)
        logger.info(f"Order cancelled: {order_id}")
    except Exception as e:
        logger.error(f"Error saving cancellation: {e}")
    return {"status": "success", "message": f"Reservation {order_id} cancelled.", "order": order}


@app.post("/restaurants/search")
async def api_search_restaurants(query: RestaurantQuery):
    return search_restaurant_information(query.model_dump())


@app.post("/reservations")
async def api_make_reservation(reservation: Reservation):
    result = make_new_order(reservation.model_dump())
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/reservations/{order_id}")
async def api_get_reservation(order_id: str):
    order = get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found.")
    return order


@app.delete("/reservations/{order_id}")
async def api_cancel_reservation(order_id: str):
    result = cancel_order(order_id)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result)
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
