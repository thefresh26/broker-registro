import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_headers(prefer: str = None) -> dict:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers

def db_get(table: str, params: dict = None):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=get_headers(),
        params=params,
    )
    response.raise_for_status()
    return response.json()

def db_post(table: str, data: dict):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=get_headers(prefer="return=representation"),
        json=data,
    )
    response.raise_for_status()
    return response.json()

def db_patch(table: str, filters: dict, data: dict):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=get_headers(prefer="return=representation"),
        params=filters,
        json=data,
    )
    response.raise_for_status()
    return response.json()

def db_delete(table: str, filters: dict):
    response = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=get_headers(),
        params=filters,
    )
    response.raise_for_status()
    return response.status_code
