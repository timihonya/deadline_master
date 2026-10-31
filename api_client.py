import certifi
import httpx
from config import TOKEN

BASE_URL = "https://platform-api2.max.ru"

async_client = httpx.AsyncClient(
    verify=certifi.where(),
    timeout=httpx.Timeout(40.0, read=100.0)
)

async def get_bot_info():
    response = await async_client.get(
        f"{BASE_URL}/me",
        headers={"Authorization": TOKEN},
    )
    response.raise_for_status()
    return response.json()

async def send_message(chat_id, text, attachments=None):
    payload = {"text": text}
    if attachments:
        payload["attachments"] = attachments

    response = await async_client.post(
        f"{BASE_URL}/messages",
        headers={
            "Authorization": TOKEN,
            "Content-Type": "application/json",
        },
        params={"chat_id": chat_id},
        json=payload,
    )
    response.raise_for_status()
    return response.json()

async def get_updates(marker=None):
    params = {"timeout": 90, "limit": 100}
    if marker is not None:
        params["marker"] = marker

    response = await async_client.get(
        f"{BASE_URL}/updates",
        headers={"Authorization": TOKEN},
        params=params,
    )
    response.raise_for_status()
    return response.json()
