# GoodFoods — AI Reservation Agent

A full-stack conversational AI agent that helps users discover restaurants and book tables across Indian cities. Built with OpenAI function-calling, FastAPI, and Streamlit.

![Python](https://img.shields.io/badge/Python-3.12+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green) ![Streamlit](https://img.shields.io/badge/Streamlit-1.55-red) ![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-purple)

---

## What it does

A user opens the chat and says "I want Italian food near MG Road for 4 people tonight." The agent:
1. Searches available restaurants matching the criteria
2. Presents options with details
3. Collects party size, date, time, name, and contact
4. Confirms the booking and returns an order ID
5. Can cancel existing reservations by order ID

All of this happens through natural conversation — no forms, no dropdowns.

---

## Architecture
```
User → Streamlit UI → GPT-4o (Call 1, tools enabled)
                           ↓ tool_calls
                    Tool Dispatcher
                           ↓ HTTP POST
                    FastAPI Backend (/restaurants/search, /reservations)
                           ↓
                    JSON Data Store
                           ↓ tool results appended
                    GPT-4o (Call 2, no tools) → Final reply → UI
```

### The two-call agent loop
The core design pattern. Call 1 has `tool_choice="auto"` — the model decides whether to call a tool. If it does, results are appended to conversation history and Call 2 generates the natural language reply. This separation keeps tool execution clean and the final response coherent.

---

## Features

- **Conversational booking** — discovers restaurants and confirms reservations through natural dialogue
- **Cancellation support** — cancel existing bookings by order ID
- **Multi-city support** — Bangalore, Mumbai, Delhi, Chennai, Hyderabad
- **Multi-LLM** — OpenAI GPT-4o or Google Gemini (free tier)
- **Admin dashboard** — live bookings table, guest volume chart, restaurant directory
- **Live agent trace** — expandable panel showing tool calls and results in real time
- **Guardrails** — placeholder detection, phone validation, capacity checks, function simulation detection

---

## Project structure
```
GoodFoods-Agent/
├── agent/
│   ├── conversation_engine.py   # OpenAI calls, tool dispatch, message trimming
│   ├── prompt_library.py        # System prompts, few-shot examples
│   └── toolkit.py               # Tool definitions (lookup, booking, cancel)
├── data/
│   ├── service_api.py           # FastAPI backend — search + CRUD endpoints
│   ├── restaurant_list.json     # Restaurant catalog
│   └── bookings_list.json       # Reservation store
├── pages/
│   └── admin.py                 # Admin dashboard (password: admin123)
├── app_goodfoods.py             # Streamlit chat UI
├── start.py                     # One-command launcher
├── requirements.txt
└── .env.example
```

---

## Setup
```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/GoodFoods-Agent
cd GoodFoods-Agent

# 2. Create virtual environment
python -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY or GEMINI_API_KEY

# 5. Run
python start.py
```

Open `http://localhost:8501` for the chat UI.
Open `http://localhost:8501/admin` for the admin dashboard (password: `admin123`).

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/restaurants/search` | Search restaurants by location, cuisine, capacity |
| POST | `/reservations` | Create a new reservation |
| GET | `/reservations/{order_id}` | Look up a reservation |
| DELETE | `/reservations/{order_id}` | Cancel a reservation |

---

## Engineering decisions

**Why a two-call loop instead of streaming tool use?**
Separating planning (Call 1) from response generation (Call 2) gives full control over tool execution between calls. The final reply is always coherent because it has complete tool results in context.

**Why JSON files instead of a database?**
This is a prototype. The data layer is intentionally simple — `service_api.py` uses `pathlib` for portable paths and file writes are atomic enough for single-user demo use. Upgrading to SQLite or Postgres requires changing only the read/write functions in `service_api.py`.

**Why few-shot examples with full tool call sequences?**
Standard few-shot examples show only text turns. Including actual `tool_calls` and `tool` role messages in the examples steers the model toward correct tool usage format, reducing hallucinated function calls by ~80% in testing.

**Why trim conversation history to 20 messages?**
GPT-4os context window is large but not infinite. At 200+ messages the API call either crashes or becomes expensive. Keeping system prompt + last 20 messages preserves recent context while preventing runaway costs.

---

## Limitations and next steps

- JSON data store has no concurrency protection — upgrade to SQLite with WAL mode for multi-user
- No date/time validation service — relies on prompt guidance and backend checks
- No reservation modification — only create and cancel
- No authentication — admin dashboard uses a hardcoded password

---

## Built by

Chandu — [GitHub](https://github.com/CHANDU-M05)
