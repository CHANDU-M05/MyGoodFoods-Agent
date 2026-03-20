"""
Tool definitions for GoodFoods reservation system.
"""

from typing import List, Dict, Union
import logging
logger = logging.getLogger('goodfoods')

restaurant_tools: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_dining_options",
            "description": """Search for restaurants based on user criteria.
- Use any specific details the user mentions: location, cuisine, party size, hours
- Empty query returns top 10 recommended restaurants
- Always returns restaurant_id needed for booking""",
            "parameters": {
                "type": "object",
                "required": [],
                "properties": {
                    "name": {"type": "string", "description": "Restaurant name"},
                    "location": {"type": "string", "description": "Area or landmark mentioned by user"},
                    "cuisine": {"type": "string", "description": "Cuisine type"},
                    "operating_hours": {
                        "type": "object",
                        "properties": {
                            "open": {"type": "string"},
                            "close": {"type": "string"}
                        }
                    },
                    "restaurant_max_seating_capacity": {"type": "integer"},
                    "max_booking_party_size": {"type": "integer"},
                    "operating_days": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_table_booking",
            "description": """Confirm a restaurant reservation.
Use ONLY after collecting all required details from the user.
- Convert relative dates (tomorrow, next Friday) to YYYY-MM-DD
- Convert times to HH:MM 24-hour format
- Verify party size fits restaurant capacity
- Never use placeholder values""",
            "parameters": {
                "type": "object",
                "required": ["restaurant_id", "orderer_name", "orderer_contact",
                             "party_size", "reservation_date", "reservation_time"],
                "properties": {
                    "restaurant_id": {"type": "string", "description": "From search results"},
                    "orderer_name": {"type": "string", "description": "Customer's actual name"},
                    "orderer_contact": {"type": "string", "description": "10-digit phone number"},
                    "party_size": {"type": "integer", "description": "Number of guests"},
                    "reservation_date": {"type": "string", "description": "YYYY-MM-DD format"},
                    "reservation_time": {"type": "string", "description": "HH:MM 24-hour format"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reservation",
            "description": """Cancel an existing reservation by order ID.
Use when the user explicitly asks to cancel a booking and provides an order ID.""",
            "parameters": {
                "type": "object",
                "required": ["order_id"],
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID to cancel e.g. ord001"}
                }
            }
        }
    }
]

logger.info("Toolkit loaded with %d tools.", len(restaurant_tools))
