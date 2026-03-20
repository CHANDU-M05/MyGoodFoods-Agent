"""
Conversation engine for GoodFoods reservation system.
"""

import json
import re
import requests
from typing import Union
from openai import OpenAI
import logging

logger = logging.getLogger('goodfoods')

BASE_URL = "http://localhost:8000"

_client: OpenAI | None = None

def _get_client(api_key: str) -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=api_key)
    return _client


def collect_user_console_message() -> dict:
    user_input = input("USER>")
    return {"role": "user", "content": user_input}


def generate_chat_completion(api_key, conversation_history: list, tools: list,
                              model_type='gpt-4o', tool_calling_enabled: bool = False):
    client = _get_client(api_key)
    if tool_calling_enabled:
        return client.chat.completions.create(
            model=model_type,
            messages=conversation_history,
            tools=tools,
            tool_choice="auto",
        )
    else:
        return client.chat.completions.create(
            model=model_type,
            messages=conversation_history,
        )


def normalize_chat_response(api_response_obj) -> Union[list, dict]:
    message = api_response_obj.choices[0].message
    if message.tool_calls:
        logger.info("Agent response includes tool calls.")
        return message.tool_calls
    elif message.content:
        logger.info("Agent response includes message content.")
        return {"role": "assistant", "content": message.content}
    return {"role": "assistant", "content": ""}


def execute_tool_calls(list_of_tool_calls: list) -> list:
    results = []
    for tool_call in list_of_tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        function_response = dispatch_backend_tool(function_name, function_args)
        if isinstance(function_response, (list, dict)):
            function_response = json.dumps(function_response)
        results.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": function_name,
            "content": function_response,
        })
        logger.info(f"Tool {function_name} executed.")
    return results


def dispatch_backend_tool(function_name: str, function_args: dict) -> Union[dict, str]:
    if function_name == 'lookup_dining_options':
        try:
            response = requests.post(f"{BASE_URL}/restaurants/search", json=function_args)
            return response.json()
        except Exception as e:
            logger.error(f"API call failed for {function_name}: {e}")
            return {"error": str(e)}
    elif function_name == 'confirm_table_booking':
        function_args.pop("capacity_debug", None)
        try:
            response = requests.post(f"{BASE_URL}/reservations", json=function_args)
            return response.json()
        except Exception as e:
            logger.error(f"API call failed for {function_name}: {e}")
            return {"error": str(e)}
    return f"No tool found with name {function_name}"


def has_function_simulation(response_text: str) -> bool:
    patterns = [
        r"<function[^>]*>",
        r"<tool[^>]*>",
        r"confirm_table_booking\([^)]*\)",
        r"lookup_dining_options\([^)]*\)",
    ]
    return any(re.search(p, response_text, re.IGNORECASE) for p in patterns)


def trim_messages(messages: list, keep_last: int = 20) -> list:
    if len(messages) <= keep_last + 1:
        return messages
    return [messages[0]] + messages[-(keep_last):]


# Patch dispatch to handle cancel_reservation
_original_dispatch = dispatch_backend_tool

def dispatch_backend_tool(function_name: str, function_args: dict) -> Union[dict, str]:
    if function_name == 'cancel_reservation':
        try:
            order_id = function_args.get("order_id", "")
            response = requests.delete(f"{BASE_URL}/reservations/{order_id}")
            return response.json()
        except Exception as e:
            logger.error(f"API call failed for {function_name}: {e}")
            return {"error": str(e)}
    return _original_dispatch(function_name, function_args)


import os
import google.generativeai as genai

def generate_chat_completion_gemini(conversation_history: list, tools: list,
                                     tool_calling_enabled: bool = False):
    """
    Gemini provider — drop-in replacement for generate_chat_completion.
    Uses GEMINI_API_KEY from environment.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Convert OpenAI message format to Gemini format
    history = []
    system_text = ""
    for msg in conversation_history:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            system_text = content
        elif role == "user":
            history.append({"role": "user", "parts": [content]})
        elif role == "assistant" and content:
            history.append({"role": "model", "parts": [content]})

    if not history:
        return None

    # Inject system prompt into first user message
    if system_text and history:
        history[0]["parts"][0] = system_text + "\n\n" + history[0]["parts"][0]

    chat = model.start_chat(history=history[:-1])
    last_message = history[-1]["parts"][0] if history else ""
    response = chat.send_message(last_message)

    return response
