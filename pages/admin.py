"""
GoodFoods Admin Dashboard
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="GoodFoods Admin",
    page_icon="🔧",
    layout="wide"
)

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    st.markdown("## Admin login")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if pwd == "admin123":
            st.session_state.admin_auth = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

BASE_DIR = Path(__file__).parent.parent / "data"

try:
    bookings = json.loads((BASE_DIR / "bookings_list.json").read_text())
except Exception:
    bookings = []

try:
    restaurants = json.loads((BASE_DIR / "restaurant_list.json").read_text())
except Exception:
    restaurants = []

restaurant_map = {r["restaurant_id"]: r["name"] for r in restaurants}

st.markdown("## GoodFoods — Admin dashboard")
st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")
if st.button("Refresh"):
    st.rerun()

st.markdown("---")

total = len(bookings)
confirmed = len([b for b in bookings if b.get("status") == "confirmed"])
cancelled = len([b for b in bookings if b.get("status") == "cancelled"])
avg_party = round(sum(b.get("party_size", 0) for b in bookings) / total, 1) if total else 0
most_booked_id = max(
    set(b["restaurant_id"] for b in bookings),
    key=lambda rid: sum(1 for b in bookings if b["restaurant_id"] == rid),
    default="—"
) if bookings else "—"
most_booked_name = restaurant_map.get(most_booked_id, most_booked_id)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total bookings", total)
c2.metric("Confirmed", confirmed)
c3.metric("Cancelled", cancelled)
c4.metric("Avg party size", avg_party)
c5.metric("Most booked", most_booked_name)

st.markdown("---")
st.markdown("### All reservations")

status_filter = st.selectbox("Filter by status", ["all", "confirmed", "cancelled"])
filtered = bookings if status_filter == "all" else [
    b for b in bookings if b.get("status") == status_filter
]

if not filtered:
    st.info("No bookings found.")
else:
    rows = [{
        "Order ID": b.get("order_id", "—"),
        "Restaurant": restaurant_map.get(b.get("restaurant_id", ""), "—"),
        "Name": b.get("orderer_name", "—"),
        "Contact": b.get("orderer_contact", "—"),
        "Party": b.get("party_size", "—"),
        "Date": b.get("reservation_date", "—"),
        "Time": b.get("reservation_time", "—"),
        "Status": b.get("status", "—"),
    } for b in filtered]
    st.dataframe(rows, width="stretch")

st.markdown("---")
st.markdown("### Bookings by time slot")

slot_counts: dict = {}
for b in bookings:
    if b.get("status") == "confirmed":
        slot = b.get("reservation_time", "unknown")
        slot_counts[slot] = slot_counts.get(slot, 0) + b.get("party_size", 0)

if slot_counts:
    sorted_slots = sorted(slot_counts.items())
    labels = [s[0] for s in sorted_slots]
    values = [s[1] for s in sorted_slots]
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.bar(labels, values, color="#334155")
    ax.set_xlabel("Time slot")
    ax.set_ylabel("Total guests")
    ax.set_title("Guest volume by time slot")
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)
else:
    st.info("No confirmed bookings to chart yet.")

st.markdown("---")
st.markdown("### Restaurants")
if restaurants:
    rows = [{
        "ID": r.get("restaurant_id", "—"),
        "Name": r.get("name", "—"),
        "Cuisine": ", ".join(r.get("cuisine", [])),
        "Max party": r.get("max_booking_party_size", "—"),
        "Capacity": r.get("restaurant_max_seating_capacity", "—"),
        "Hours": f"{r.get('operating_hours',{}).get('open','?')} - {r.get('operating_hours',{}).get('close','?')}",
    } for r in restaurants]
    st.dataframe(rows, width="stretch")
else:
    st.info("No restaurant data.")
