import asyncio
import httpx
import logging
from config import TOKEN

logger = logging.getLogger(__name__)
BASE_URL = "https://platform-api2.max.ru"

async_client = httpx.AsyncClient(
    verify=False,
    timeout=httpx.Timeout(40.0, read=100.0)
)

async def send_message(chat_id=None, user_id=None, text="", attachments=None):
    payload = {
        "text": text,
        "format": "markdown"
    } 
    if attachments:
        payload["attachments"] = attachments

    params = {}
    if user_id:
        params["user_id"] = int(user_id)
    elif chat_id:
        params["chat_id"] = int(chat_id)
    else:
        raise ValueError("Ошибка: нужно передать chat_id или user_id")

    response = await async_client.post(
        f"{BASE_URL}/messages",
        headers={
            "Authorization": TOKEN,
            "Content-Type": "application/json",
        },
        params=params,
        json=payload,
    )
    response.raise_for_status()
    result = response.json()
    return result

async def _upload_image(image_io) -> str:
    """
    Внутренняя функция для загрузки изображения.
    Возвращает токен загруженного файла.
    """
    # 1. Запрашиваем URL для загрузки
    upload_resp = await async_client.post(
        f"{BASE_URL}/uploads",
        headers={"Authorization": TOKEN},
        params={"type": "image"}
    )
    upload_resp.raise_for_status()
    upload_data = upload_resp.json()
    
    upload_url = upload_data.get("url")
    if not upload_url:
        raise ValueError(f"API не вернул URL для загрузки: {upload_data}")

    # 2. Загружаем файл по полученному URL
    # MAX ожидает файл в поле 'data' (multipart/form-data)
    files = {"data": ("profile.png", image_io, "image/png")}
    file_resp = await async_client.post(upload_url, files=files)
    file_resp.raise_for_status()
    file_data = file_resp.json()

    # 3. Извлекаем токен из вложенной структуры photos
    token = None
    if "photos" in file_data and isinstance(file_data["photos"], dict):
        # Берем первый попавшийся ключ (обычно "0", "photoIds" и т.д.)
        for key, photo_data in file_data["photos"].items():
            if isinstance(photo_data, dict) and "token" in photo_data:
                token = photo_data["token"]
                break

    # На случай, если API вернет токен в корне (для обратной совместимости)
    if not token:
        token = file_data.get("token")

    if not token:
        raise ValueError(f"API не вернул токен после загрузки. Ответ: {file_data}")
    
    logger.info(f"Изображение успешно загружено, токен: {token[:20]}...")
    return token


async def send_photo(user_id, text, image_io, attachments=None):
    """
    Отправляет изображение, выполняя двухэтапную загрузку.
    """
    # 1. Загружаем изображение и получаем токен
    image_token = await _upload_image(image_io)

    # 2. Небольшая пауза, чтобы сервер MAX успел обработать файл (рекомендуется)
    await asyncio.sleep(0.25)

    # 3. Формируем вложение с токеном согласно спецификации API2
    image_attachment = {
        "type": "image",
        "payload": {
            "token": image_token
        }
    }
    
    # 4. Собираем все вложения (изображение + клавиатура)
    final_attachments = [image_attachment]
    if attachments:
        final_attachments.extend(attachments)

    payload = {
        "text": text,
        "format": "markdown",
        "attachments": final_attachments
    }

    # 5. Отправляем сообщение с токеном
    response = await async_client.post(
        f"{BASE_URL}/messages",
        headers={
            "Authorization": TOKEN,
            "Content-Type": "application/json",
        },
        params={"user_id": int(user_id)},
        json=payload,
    )
    response.raise_for_status()
    return response.json()

async def answer_callback(callback_id, text, image_io=None, attachments=None):
    payload = {
        "message": {
            "text": text,
            "format": "markdown"
        }
    }
    final_attachments = []
    if attachments:
        final_attachments.extend(attachments)
    if image_io:
        image_token = await _upload_image(image_io)
        await asyncio.sleep(0.25)
        
        image_attachment = {
            "type": "image",
            "payload": {
                "token": image_token
            }
        }
        final_attachments.append(image_attachment)
    if final_attachments:
        payload["message"]["attachments"] = final_attachments

    response = await async_client.post(
        f"{BASE_URL}/answers",
        headers={
            "Authorization": TOKEN,
            "Content-Type": "application/json",
        },
        params={"callback_id": callback_id},
        json=payload,
    )
    response.raise_for_status()
    return response.json()

async def get_messages(chat_id, _from=None, to=None, count=None):
    params = {"chat_id": int(chat_id)}
    if _from:
        params["from"] = _from
    if to:
        params["to"] = to
    if count:
        params["count"] = count
    
    response = await async_client.get(
        f"{BASE_URL}/messages",
        headers={"Authorization": TOKEN},
        params=params
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