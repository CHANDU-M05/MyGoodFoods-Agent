"""
GoodFoods Reservation Assistant — Streamlit UI
"""

from dotenv import load_dotenv
import os
from pathlib import Path
import streamlit as st
import json
import logging

from agent.conversation_engine import (
    generate_chat_completion,
    normalize_chat_response,
    execute_tool_calls,
    has_function_simulation,
    trim_messages,
)
from agent.toolkit import restaurant_tools
from agent.prompt_library import (
    restaurant_test_conversation_system_prompt_w_fewshot,
    get_current_time,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('goodfoods')

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# ── Page config ──
st.set_page_config(
    page_title="GoodFoods Reservation Assistant",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
  .stButton>button {
    background-color: #1f2937; color: #f8fafc;
    border-radius: 10px; border: 1px solid #475569;
  }
  .stButton>button:hover { background-color: #334155; }
  .stChatMessage { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──
with st.sidebar:
    st.markdown("## GoodFoods")

    # City selector — multi-city support
    # WHY: hardcoding Bangalore limits the project to a demo.
    # City selection updates the system prompt context dynamically.
    provider = st.selectbox("LLM Provider", ["Gemini (free)", "OpenAI"], index=0)

    city = st.selectbox(
        "City",
        ["Bangalore", "Mumbai", "Delhi", "Chennai", "Hyderabad"],
        index=0
    )

    st.markdown("---")
    st.button("Restart conversation", on_click=lambda: st.session_state.clear())
    st.markdown("---")
    st.page_link("pages/admin.py", label="Admin dashboard", icon="🔧")

# ── Build system prompt with current time + selected city ──
def build_system_prompt(city: str) -> str:
    base = restaurant_test_conversation_system_prompt_w_fewshot
    # Inject city into the prompt
    return base.replace("Bangalore", city).replace(
        "{get_current_time()}",
        get_current_time()
    )

# ── Session state init ──
welcome = f"Hello! I'm here to help with your reservation at GoodFoods in {city}. Ask me for recommendations or book a table."

if "messages" not in st.session_state or st.session_state.get("city") != city:
    st.session_state.city = city
    st.session_state.messages = [
        {"role": "system", "content": build_system_prompt(city)},
        {"role": "assistant", "content": welcome},
    ]

# ── Header ──
st.markdown(f"## GoodFoods — {city}")
st.caption("Powered by Agentic AI · Book tables across your city")

# ── Render chat history ──
for message in st.session_state.messages:
    if message["role"] not in ["system", "tool"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# ── Chat input ──
if prompt := st.chat_input("Ask about restaurants or make a reservation..."):
    if not openai_api_key or openai_api_key == "sk-placeholder":
        st.error("OPENAI_API_KEY not found. Add it to your .env file.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        trace = st.expander("Agent thinking & tool activity", expanded=True)
        with trace:
            st.markdown("**Request received** — planning...")
            trace_plan = st.empty()
            trace_tools = st.empty()
            trace_results = st.empty()
            trace_final = st.empty()

        with st.spinner("Thinking..."):
            trimmed = trim_messages(st.session_state.messages, keep_last=20)
            if provider == "Gemini (free)":
                from agent.conversation_engine import generate_chat_completion_gemini
                try:
                    gemini_resp = generate_chat_completion_gemini(trimmed, restaurant_tools, tool_calling_enabled=True)
                    if gemini_resp:
                        content = gemini_resp.text
                        st.markdown(content)
                        st.session_state.messages.append({"role": "assistant", "content": content})
                except Exception as e:
                    st.error(f"Gemini error: {e}")
                st.stop()
            try:

                api_response = generate_chat_completion(
                    api_key=openai_api_key,
                    conversation_history=trimmed,
                    tools=restaurant_tools,
                    tool_calling_enabled=True
                )
            except Exception as e:
                logger.error(f"API call failed: {e}", exc_info=True)
                st.error("API call failed. Please restart the conversation.")
                st.stop()

        formatted = normalize_chat_response(api_response)
        assistant_msg = api_response.choices[0].message

        with trace:
            if assistant_msg and (assistant_msg.content or "").strip():
                trace_plan.markdown(f"**Plan**\n\n{assistant_msg.content}")
            if assistant_msg and assistant_msg.tool_calls:
                summaries = [
                    f"- `{tc.function.name}` → `{tc.function.arguments[:200]}`"
                    for tc in assistant_msg.tool_calls
                ]
                trace_tools.markdown("**Tool calls**\n\n" + "\n".join(summaries))

        # ── Direct text response (no tool calls) ──
        if not isinstance(formatted, list):
            content = formatted.get("content", "")
            if has_function_simulation(content):
                logger.warning("Function simulation detected.")
                st.error("Something went wrong. Please restart the conversation.")
                st.stop()
            st.markdown(content)
            st.session_state.messages.append(formatted)

        # ── Tool call response ──
        else:
            placeholder = st.empty()
            placeholder.markdown("Finding options for you...")

            # Append assistant tool_calls message first
            try:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in (assistant_msg.tool_calls or [])
                    ],
                })
            except Exception as e:
                logger.error(f"Failed to append tool_calls message: {e}")

            tool_messages = execute_tool_calls(formatted)
            st.session_state.messages.extend(tool_messages)

            with trace:
                rendered = [
                    f"- `{tm.get('name')}` → `{str(tm.get('content',''))[:200]}`"
                    for tm in tool_messages
                ]
                trace_results.markdown("**Tool results**\n\n" + "\n".join(rendered))

            # Second API call — no tools, generate final reply
            try:
                trimmed2 = trim_messages(st.session_state.messages, keep_last=20)
                updated = generate_chat_completion(
                    api_key=openai_api_key,
                    conversation_history=trimmed2,
                    tools=restaurant_tools,
                    tool_calling_enabled=False
                )
            except Exception as e:
                logger.error(f"Follow-up API call failed: {e}", exc_info=True)
                st.error("Follow-up API call failed. Please restart.")
                st.stop()

            final = normalize_chat_response(updated)
            final_content = final.get("content", "")
            placeholder.markdown(final_content)
            st.session_state.messages.append(final)

            with trace:
                trace_final.markdown(f"**Final response**\n\n{final_content}")
