"""
Start both FastAPI backend and Streamlit frontend in one command.
Usage: python start.py
"""
import subprocess
import threading
import time
import requests
import os

def start_api():
    subprocess.Popen(["uvicorn", "data.service_api:app", "--host", "0.0.0.0", "--port", "8000"])

def start_ui():
    subprocess.run(["streamlit", "run", "app_goodfoods.py"])

if __name__ == "__main__":
    print("Starting FastAPI backend...")
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    print("Waiting for API to be ready...")
    for _ in range(10):
        try:
            requests.get("http://localhost:8000/docs", timeout=2)
            print("API ready at http://localhost:8000")
            break
        except Exception:
            time.sleep(1)

    print("Starting Streamlit UI...")
    start_ui()
