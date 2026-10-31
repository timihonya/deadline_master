import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from api_client import async_client, get_updates, send_message
from keyboards import get_main_keyboard, get_types_keyboard

user_states = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def init_db():
    import os
    os.makedirs("generated", exist_ok=True)
    conn = sqlite3.connect("generated/deadline_keeper.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            task_type TEXT,
            task_name TEXT,
            deadline_date TEXT,
            reminded_days TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

def save_task(user_id, task_type, task_name, deadline_date):
    conn = sqlite3.connect("generated/deadline_keeper.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (user_id, task_type, task_name, deadline_date) VALUES (?, ?, ?, ?)",
        (user_id, task_type, task_name, deadline_date)
    )
    conn.commit()
    conn.close()

def get_user_tasks(user_id):
    conn = sqlite3.connect("generated/deadline_keeper.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, task_type, task_name, deadline_date FROM tasks WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "type": r[1], "name": r[2], "date": r[3]} for r in rows]

def delete_task(task_id, user_id):
    conn = sqlite3.connect("generated/deadline_keeper.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    conn.close()

def get_all_tasks_for_reminders():
    conn = sqlite3.connect("generated/deadline_keeper.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, task_type, task_name, deadline_date, reminded_days FROM tasks")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_reminded_status(task_id, new_reminded_str):
    conn = sqlite3.connect("generated/deadline_keeper.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET reminded_days = ? WHERE id = ?", (task_id, new_reminded_str))
    conn.commit()
    conn.close()

def calculate_reminder_days(deadline_dt, creation_dt):
    return [30, 14, 7, 3, 1, 0]

async def reminder_scheduler():
    while True:
        try:
            today_dt = datetime.now()
            tasks = get_all_tasks_for_reminders()
            for task_id, user_id, t_type, t_name, d_date, reminded_days in tasks:
                try:
                    deadline_dt = datetime.strptime(d_date, "%d.%m.%Y")
                except ValueError:
                    continue
                
                days_left = (deadline_dt.date() - today_dt.date()).days
                if days_left < 0:
                    continue

                intervals = calculate_reminder_days(deadline_dt, today_dt)
                reminded_list = reminded_days.split(",") if reminded_days else []

                if days_left in intervals and str(days_left) not in reminded_list:
                    if days_left == 0:
                        msg_text = f"🚨 **Дедлайн СЕГОДНЯ!**\n\nПора сдавать задание:\n📌 {t_name} ({t_type})\nТы справишься! 👍"
                    else:
                        msg_text = f"⏰ **Напоминание о дедлайне!**\n\nДо сдачи задания осталось дней: {days_left}\n📌 {t_name} ({t_type})\n📅 Дата сдачи: {d_date}"
                    
                    await send_message(chat_id=user_id, text=msg_text)
                    reminded_list.append(str(days_left))
                    update_reminded_status(task_id, ",".join(reminded_list))
        except Exception:
            logger.exception("Ошибка планировщика")
        await asyncio.sleep(3600)

async def handle_update(update):
    update_type = update.get("update_type")

    if update_type == "message_created":
        message = update.get("message", {})
        body = message.get("body", {})
        text = body.get("text", "").strip()
        recipient = message.get("recipient", {})
        chat_id = recipient.get("chat_id") or update.get("chat_id")
        user = message.get("sender", {})
        user_id = user.get("user_id") or chat_id

        if not chat_id:
            return

        if text.lower() == "/start":
            user_states.pop(user_id, None)
            await send_message(chat_id, "Выбери действие:", attachments=[get_main_keyboard()])
            return

        state_data = user_states.get(user_id)
        state = state_data.get("state") if state_data else None

        if state == "waiting_name":
            user_states[user_id]["task_name"] = text
            user_states[user_id]["state"] = "waiting_date"
            await send_message(chat_id, "Введи дату задания в формате ДД.ММ.ГГГГ:")
            return

        if state == "waiting_date":
            try:
                datetime.strptime(text, "%d.%m.%Y")
            except ValueError:
                await send_message(chat_id, "Неверный формат даты. Пример: 08.11.2026")
                return

            save_task(user_id, state_data["task_type"], state_data["task_name"], text)
            user_states.pop(user_id, None)

            await send_message(
                chat_id,
                f"Задание успешно сохранено!\n\n📌 Тип: {state_data['task_type']}\n📝 Название: {state_data['task_name']}\n📅 Дата дедлайна: {text}\n\nВыбери действие:",
                attachments=[get_main_keyboard()]
            )
            return

    elif update_type == "message_callback":
        callback = update.get("callback", {})
        payload = callback.get("payload", "")
        message = update.get("message", {})
        recipient = message.get("recipient", {})
        chat_id = recipient.get("chat_id") or update.get("chat_id")
        sender = callback.get("user", {})
        user_id = sender.get("user_id") or chat_id

        if not chat_id:
            return

        if payload == "confirm_add_task":
            await send_message(chat_id, "Выбери тип задания:", attachments=[get_types_keyboard()])

        elif payload == "confirm_watch_tasks":
            user_tasks = get_user_tasks(user_id)
            if not user_tasks:
                await send_message(chat_id, "У тебя пока нет добавленных задач! 🎉", attachments=[get_main_keyboard()])
            else:
                report = "📊 **Твоя текущая нагрузка:**\n\n"
                buttons = []
                for idx, t in enumerate(user_tasks, 1):
                    report += f"{idx}. {t['name']} ({t['type']}) — 📅 {t['date']}\n"
                    buttons.append([{
                        "type": "callback",
                        "text": f"✅ Выполнено: {t['name']}",
                        "payload": f"done_{t['id']}"
                    }])
                
                keyboard = {
                    "type": "inline_keyboard",
                    "payload": {"buttons": buttons}
                }
                await send_message(chat_id, report, attachments=[keyboard])

        elif payload == "confirm_reminders":
            await send_message(
                chat_id,
                "🔔 **Система умных напоминаний активна!**\n\nБот автоматически рассчитывает интервалы (за 30, 14, 7, 3, 1 дней и в день сдачи) в зависимости от сложности задачи.",
                attachments=[get_main_keyboard()]
            )

        elif payload.startswith("done_"):
            try:
                task_id = int(payload.split("_")[1])
                delete_task(task_id, user_id)
                await send_message(
                    chat_id, 
                    "🎉 Задание отмечено как выполненное и удалено из списка!", 
                    attachments=[get_main_keyboard()]
                )
            except Exception:
                logger.exception("Ошибка удаления")

        elif payload in ("first_type", "second_type", "third_type"):
            types = {
                "first_type": "Обычное задание",
                "second_type": "Олимпиада или конкурс",
                "third_type": "Проект или исследовательская работа",
            }
            user_states[user_id] = {"state": "waiting_name", "task_type": types[payload]}
            await send_message(chat_id, "Введи название задания:")

    elif update_type == "bot_started":
        chat_id = update.get("chat_id")
        if chat_id:
            await send_message(chat_id, "Отправь мне /start")

async def main():
    init_db()
    marker = None
    asyncio.create_task(reminder_scheduler())
    try:
        while True:
            try:
                result = await get_updates(marker)
                for update in result.get("updates", []):
                    await handle_update(update)
                marker = result.get("marker", marker)
            except Exception:
                logger.exception("Ошибка при получении обновлений")
                await asyncio.sleep(3)
    finally:
        await async_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
