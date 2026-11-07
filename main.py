import asyncio
import logging
import sqlite3
import os
import io 
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

from keyboards import get_main_keyboard, get_types_keyboard, get_calendar_keyboard, get_shop_keyboard
from api_client import async_client, get_updates, send_message, edit_message, answer_callback, send_photo

user_states = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_TASKS = "generated/deadline_keeper.db"
DB_USERS = "generated/users_info.db"

# ================= это база заданий =================

def init_db():
    os.makedirs("generated", exist_ok=True)
    with sqlite3.connect(DB_TASKS) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                chat_id TEXT,
                task_type TEXT,
                task_name TEXT,
                deadline_date TEXT,
                reminded_days TEXT DEFAULT ''
            )
        """)

def save_task(user_id, chat_id, task_type, task_name, deadline_date):
    with sqlite3.connect(DB_TASKS) as conn:
        conn.execute(
            "INSERT INTO tasks (user_id, chat_id, task_type, task_name, deadline_date) VALUES (?, ?, ?, ?, ?)",
            (user_id, chat_id, task_type, task_name, deadline_date)
        )

def get_user_tasks(user_id):
    with sqlite3.connect(DB_TASKS) as conn:
        cursor = conn.execute("SELECT id, task_type, task_name, deadline_date FROM tasks WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
    return [{"id": r[0], "type": r[1], "name": r[2], "date": r[3]} for r in rows]

def delete_task(task_id, user_id):
    with sqlite3.connect(DB_TASKS) as conn:
        conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))

def get_all_tasks_for_reminders():
    with sqlite3.connect(DB_TASKS) as conn:
        cursor = conn.execute("SELECT id, user_id, chat_id, task_type, task_name, deadline_date, reminded_days FROM tasks")
        rows = cursor.fetchall()
    return rows

def update_reminded_status(task_id, new_reminded_str):
    with sqlite3.connect(DB_TASKS) as conn:
        conn.execute("UPDATE tasks SET reminded_days = ? WHERE id = ?", (new_reminded_str, task_id))


# ================= а це база пользователей =================

def init_users_db():
    os.makedirs("generated", exist_ok=True)
    with sqlite3.connect(DB_USERS) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                chat_id TEXT,
                exp INTEGER DEFAULT 0,
                coins INTEGER DEFAULT 0,
                tasks_done INTEGER DEFAULT 0
            ) 
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_streak(
                user_id TEXT PRIMARY KEY,
                curr_streak INTEGER DEFAULT 0,
                max_streak INTEGER DEFAULT 0,
                last_active_date TEXT
            )
        """)

def add_new_user(user_id, chat_id):
    with sqlite3.connect(DB_USERS) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, chat_id, exp, coins, tasks_done) VALUES (?, ?, 0, 0, 0)",
            (user_id, chat_id)
        )
        conn.execute("UPDATE users SET chat_id = ? WHERE user_id = ?", (chat_id, user_id))

def update_user_info(user_id, exp=None, coins=None, task_done=None):
    with sqlite3.connect(DB_USERS) as conn:
        if exp is not None:
            conn.execute("UPDATE users SET exp = exp + ? WHERE user_id = ?", (exp, user_id)) 
        if coins is not None:
            conn.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (coins, user_id))
        if task_done:
            conn.execute("UPDATE users SET tasks_done = tasks_done + 1 WHERE user_id = ?", (user_id,))

def get_user_exp_coins(user_id):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.execute("SELECT exp, coins FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    return {"exp": row[0], "coins": row[1]} if row else {"exp": 0, "coins": 0}

def get_user_stats(user_id):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.execute("SELECT exp, coins, tasks_done FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    return {"exp": row[0], "coins": row[1], "tasks_done": row[2]} if row else {"exp": 0, "coins": 0, "tasks_done": 0}

def update_streak(user_id, today):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.execute("SELECT curr_streak, max_streak, last_active_date FROM user_streak WHERE user_id = ?", (str(user_id),))
        row = cursor.fetchone()
        
        if not row:
            conn.execute(
                "INSERT INTO user_streak (user_id, curr_streak, max_streak, last_active_date) VALUES (?, 1, 1, ?)", 
                (str(user_id), today)
            )
            return 1
            
        curr_streak, max_streak, last_active = row
        if last_active == today:
            return curr_streak
            
        today_dt = datetime.strptime(today, "%Y-%m-%d").date()
        last_active_dt = datetime.strptime(last_active, "%Y-%m-%d").date()
        diff = (today_dt - last_active_dt).days
        
        if diff == 1:
            curr_streak += 1
        else:
            curr_streak = 1
            
        max_streak = max(max_streak, curr_streak)
        conn.execute(
            "UPDATE user_streak SET curr_streak = ?, max_streak = ?, last_active_date = ? WHERE user_id = ?", 
            (curr_streak, max_streak, today, str(user_id))
        )
        return curr_streak

def get_user_streak(user_id):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.execute("SELECT curr_streak FROM user_streak WHERE user_id = ?", (str(user_id),))
        row = cursor.fetchone()
    return row[0] if row else 0


# ================= магазин =================

def create_shop_tasks():
    with sqlite3.connect(DB_USERS) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, 
                category TEXT NOT NULL, 
                price INTEGER NOT NULL,
                rarity TEXT,
                image_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                purchase_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS equipped_items (
                user_id TEXT PRIMARY KEY,
                avatar_id INTEGER NOT NULL
            )
        """)

def add_avatar(name, price, rarity, image_path):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM shop_items WHERE name = ? AND category = 'avatar'", (name,))
        if cursor.fetchone():
            return
        cursor.execute("""
            INSERT INTO shop_items (name, category, price, rarity, image_path)
            VALUES (?, 'avatar', ?, ?, ?)
        """, (name, price, rarity, image_path))

def init_shop():
    avatars = [
        ("Котик сигма", 50, "Обычная", "profile_images/cool_cat.png"),
        ("Лиса школьница", 50, "Обычная", "profile_images/pupil_fox.png"),
        ("Дракоша", 70, "Редкая", "profile_images/dragon.png"),
        ("Умная сова", 70, "Редкая", "profile_images/clever_owl.png"),
        ("Король Лягуш", 100, "Эпическая", "profile_images/king_frog.png"),
        ("КосмоРобот", 100, "Эпическая", "profile_images/space_robot.png"),
        ("Хранитель времени", 150, "Мифическая", "profile_images/keeper.png"),
        ("Милый зайка", 150, "Мифическая", "profile_images/lovely_bunny.png"),
        ("Легенда времени", 250, "Легендарная", "profile_images/idk_who_is_that.png")
    ]
    for avatar in avatars:
        add_avatar(*avatar)

def get_shop_items():
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.execute("""
            SELECT id, name, price, rarity, image_path
            FROM shop_items
            WHERE category = 'avatar'
            ORDER BY id
        """)
        return cursor.fetchall()

def has_avatar(user_id, item_id):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.execute("SELECT id FROM user_inventory WHERE user_id = ? AND item_id = ?", (str(user_id), item_id))
        return cursor.fetchone() is not None

def buy_avatar(user_id, item_id):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT price FROM shop_items WHERE id = ? AND category = 'avatar'", (item_id,))
        item = cursor.fetchone()
        if not item:
            return False, "Аватарка не найдена."
            
        cursor.execute("SELECT id FROM user_inventory WHERE user_id = ? AND item_id = ?", (str(user_id), item_id))
        if cursor.fetchone():
            return False, "Эта аватарка уже куплена."
            
        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (str(user_id),))
        user = cursor.fetchone()
        if not user:
            return False, "Пользователь не найден."
            
        price = item[0]
        if user[0] < price:
            return False, "Недостаточно монет."
            
        cursor.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (price, str(user_id)))
        cursor.execute("INSERT INTO user_inventory (user_id, item_id) VALUES (?, ?)", (str(user_id), item_id))
        
        return True, "Аватарка успешно куплена!"

async def show_shop(user_id, index=0, callback_id=None):
    items = await asyncio.to_thread(get_shop_items)

    if not items:
        await send_message(user_id=user_id, text="Магазин пока пуст")
        return

    index = index % len(items)
    item = items[index]
    item_id, name, price, rarity, image_path = item

    bought = await asyncio.to_thread(has_avatar, user_id, item_id)
    equipped_id = await asyncio.to_thread(get_equipped_avatar, user_id)
    equipped = equipped_id == item_id

    text = (
        f"🛍️ {name}\n\n"
        f"✨ Редкость: {rarity}\n"
        f"🪙 Цена: {price} монет\n"
        f"📦 {index+1}/{len(items)}"
    )

    keyboard = get_shop_keyboard(item_id, bought, equipped)

    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            image_bytes = io.BytesIO(image_file.read())
        if callback_id: 
            await answer_callback(
                callback_id=callback_id,
                text=text,
                image_io=image_bytes,
                attachments=[keyboard]
            )
        else:
            await send_photo(
                user_id=user_id,
                text=text,
                image_io=image_bytes,
                attachments=[keyboard]
            )
    else:
        await send_message(
            user_id=user_id,
            text=text + "\n Изображение не найдено",
            attachments=[keyboard]
        )
    user_states[user_id] = {"state": "shop", "index": index}

def equip_avatar(user_id, item_id):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM user_inventory WHERE user_id = ? AND item_id = ?", (str(user_id), item_id))
        if cursor.fetchone() is None:
            return False
            
        cursor.execute("""
            INSERT INTO equipped_items (user_id, avatar_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET avatar_id = excluded.avatar_id
        """, (str(user_id), item_id))
        return True

def get_equipped_avatar(user_id):
    with sqlite3.connect(DB_USERS) as conn:
        cursor = conn.execute("SELECT avatar_id FROM equipped_items WHERE user_id = ?", (str(user_id),))
        result = cursor.fetchone()
        return result[0] if result else None


# ================= картинка и всё остальное =================

def generate_profile_card(username, level, coins, exp, streak, total_completed):
    img = Image.new("RGB", (600, 450), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    try:
        font_title = ImageFont.truetype(font_path, 32)
        font_sub = ImageFont.truetype(font_path, 18)
        font_big = ImageFont.truetype(font_path, 40)
    except IOError:
        try:
            font_title = ImageFont.truetype("Arial.ttf", 32)
            font_sub = ImageFont.truetype("Arial.ttf", 18)
            font_big = ImageFont.truetype("Arial.ttf", 40)
        except IOError:
            font_title = font_sub = font_big = ImageFont.load_default()

    draw.text((30, 25), "Профиль", fill="#000000", font=font_title)
    draw.rounded_rectangle([440, 25, 570, 65], radius=8, fill="#E6D8FF")
    draw.text((455, 34), f"Уровень {level}", fill="#7F49F2", font=font_sub)

    draw.rounded_rectangle([30, 90, 150, 210], radius=12, fill="#F0F2F5")
    draw.rectangle([75, 135, 105, 165], outline="#99A2AD", width=2)

    draw.text((170, 95), username, fill="#000000", font=font_title)
    draw.text((170, 170), f"{coins}", fill="#E6A23C", font=font_title)

    exp_need = 100
    exp_in_level = exp
    while exp_in_level > exp_need:
        exp_in_level -= exp_need
        exp_need += 100
    
    draw.text((30, 240), "Опыт", fill="#000000", font=font_title)
    draw.text((460, 248), f"{exp_in_level} / {exp_need} EXP", fill="#7E8B9A", font=font_sub)

    draw.rounded_rectangle([30, 285, 570, 310], radius=10, fill="#F0F2F5")

    progress = 30 + int((540 * (exp_in_level / exp_need)))
    if progress > 30:
        draw.rounded_rectangle([30, 285, progress, 310], radius=10, fill="#9A66FF")

    draw.text((30, 345), f"{streak}", fill="#FF7A00", font=font_big)
    draw.text((30, 395), "Дней подряд", fill="#5C6673", font=font_sub)

    draw.text((330, 345), f"{total_completed}", fill="#000000", font=font_big)
    draw.text((330, 395), "Выполнено заданий", fill="#5C6673", font=font_sub)

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return img_byte_arr

async def reminder_scheduler():
    while True:
        try:
            today_dt = datetime.now()
            tasks = await asyncio.to_thread(get_all_tasks_for_reminders)

            for task in tasks:
                try:
                    task_id, user_id, chat_id, t_type, t_name, d_date, reminded_days = task

                    try:
                        deadline_dt = datetime.strptime(d_date, "%d.%m.%Y")
                    except ValueError:
                        logger.warning(f"Неверный формат даты для задачи {task_id}: {d_date}")
                        continue

                    days_left = (deadline_dt.date() - today_dt.date()).days
                    if days_left < 0:
                        continue

                    intervals = [30, 14, 7, 3, 1, 0]
                    reminded_list = reminded_days.split(",") if reminded_days else []

                    if days_left in intervals and str(days_left) not in reminded_list:
                        if days_left == 0:
                            msg_text = f"🚨 **Дедлайн СЕГОДНЯ!**\n\nПора сдавать задание:\n📌 {t_name} ({t_type})\nТы справишься! 👍"
                        else:
                            msg_text = f"⏰ **Напоминание о дедлайне!**\n\nДо сдачи задания осталось дней: {days_left}\n📌 {t_name} ({t_type})\n📅 Дата сдачи: {d_date}"

                        if chat_id:
                            await send_message(chat_id=chat_id, text=msg_text)
                        else:
                            await send_message(user_id=user_id, text=msg_text)

                        reminded_list.append(str(days_left))
                        await asyncio.to_thread(update_reminded_status, task_id, ",".join(reminded_list))

                except Exception as task_error:
                    logger.error(f"Ошибка при обработке напоминания для задачи {task[0]}: {task_error}")

        except Exception:
            logger.exception("Критическая ошибка планировщика")

        await asyncio.sleep(3600)


async def handle_update(update):
    update_type = update.get("update_type")
    message = update.get("message", {})
    callback = update.get("callback", {})

    callback_msg = callback.get("message", {})
    current_message_id = None
    if callback_msg:
        body = callback_msg.get("body", {})
        if body:
            current_message_id = body.get("mid")
        if not current_message_id:
            current_message_id = callback_msg.get("mid") or callback_msg.get("message_id")
    
    if not current_message_id:
        current_message_id = callback.get("mid")

    chat_id = None
    user_id = None

    if update_type == "message_created":
        chat_id = message.get("chat_id") or message.get("recipient", {}).get("chat_id")
        user_id = message.get("sender", {}).get("user_id")
    elif update_type == "message_callback":
        chat_id = callback.get("message", {}).get("recipient", {}).get("chat_id") or callback.get("message", {}).get("chat_id")
        user_id = callback.get("user", {}).get("user_id")
    elif update_type == "bot_started":
        chat_id = update.get("chat_id")
        user_id = chat_id

    if not user_id:
        logger.warning(f"Не удалось определить user_id для обновления: {update_type}")
        return

    if update_type in ("message_created", "message_callback", "bot_started"):
        await asyncio.to_thread(add_new_user, user_id, chat_id)
        today = datetime.now().strftime("%Y-%m-%d")
        curr_streak = await asyncio.to_thread(update_streak, user_id, today)

    if update_type == "message_created":
        body = message.get("body", {})
        text = body.get("text", "").strip()

        if text.lower() == "/start":
            user_states.pop(user_id, None)
            menu_text = (
                "📋Главное меню функций\n\n"
                " Выбери, что ты хочешь сделать: \n"
                "➕ Добавить задачу - внести новое задание или проект\n"
                "📊 Моя нагрузка - посмотреть список текущих заданий и отменить их\n"
                "🔔 Напоминания - проверить статус работы напоминаний"
            )
            await send_message(user_id=user_id, text=menu_text, attachments=[get_main_keyboard()])
            return

        if text.lower() == "/give_meh_money":
            await asyncio.to_thread(update_user_info, user_id, coins = 2000)

        state_data = user_states.get(user_id)
        state = state_data.get("state") if state_data else None

        if state == "waiting_name":
            user_states[user_id]["task_name"] = text
            user_states[user_id]["state"] = "waiting_date"
            now = datetime.now()
            keyboard = get_calendar_keyboard(now.month, now.year)
            await send_message(user_id=user_id, text="Выбери дату", attachments=keyboard)
            return

        if state == "waiting_date":
            await send_message(user_id=user_id, text="Пожалуйста, выбери дату из календаря выше 👆")
            return

    elif update_type == "bot_started":
        welcome_message = (
            " 👋 Приветствую! Я твой персональный Дедлайн-хранитель\n\n"
            "Помогу держать под контролем все школьные задания\n"
            "Буду автоматически рассчитывать нагрузку и присылать напоминания\n"
            "👇Отправь мне /start, чтобы увидеть все функции"
        )
        await send_message(user_id=user_id, text=welcome_message)
        return

    elif update_type == "message_callback":
        payload = callback.get("payload", "")

        if payload == "cal_ignore":
            return

        if payload == "confirm_add_task":
            await send_message(user_id=user_id, text="Выбери тип задания:", attachments=[get_types_keyboard()])

        elif payload == "confirm_open_shop":
            await show_shop(user_id)
            return

        elif payload.startswith("shop_buy_"):
            item_id = int(payload.split("_")[-1])

            success, message_text = await asyncio.to_thread(
                buy_avatar, user_id, item_id
            )

            await send_message(user_id=user_id, text=message_text)

            if success:
                state_data = user_states.get(user_id, {})
                await show_shop(user_id, state_data.get("index", 0))

        elif payload.startswith("shop_equip_"):
            item_id = int(payload.split("_")[-1])  # поставь стикер на Аватарка установлена, пожалуйста, в 532 строке
            success = await asyncio.to_thread(equip_avatar, user_id, item_id)

            if success:
                await send_message(user_id=user_id, text= "Аватарка установлена")
                state_data= user_states.get(user_id, {})
                await show_shop(user_id, state_data.get("index", 0))

            else:
                await send_message(user_id=user_id, text= "Сначала купи аватарку")

        elif payload in ("shop_prev", "shop_next"):
            state_data = user_states.get(user_id, {})
            index = state_data.get("index", 0)

            if payload == "shop_prev":
                index -= 1
            else:
                index += 1
            callback_id = callback.get("callback_id")
            await show_shop(user_id, index, callback_id=callback_id) 
            return
        
        elif payload == "shop_current":
            await send_message(user_id= user_id, text = "Эта аватарка уже установлена")

        elif payload == "confirm_watch_tasks":
            user_tasks = await asyncio.to_thread(get_user_tasks, user_id)
            if not user_tasks:
                await send_message(user_id=user_id, text="У тебя пока нет добавленных задач! 🎉", attachments=[get_main_keyboard()])
            else:
                report = "📊 **Твоя текущая нагрузка:**\n\n"
                buttons = []
                for idx, t in enumerate(user_tasks, 1):
                    report += f"{idx}. {t['name']} ({t['type']}) — 📅 {t['date']}\n"
                    buttons.append([{
                        "type": "callback",
                        "text": f"✅ Завершить: {t['name']}",
                        "payload": f"done_{t['id']}"
                    }])
                buttons.append([{
                    "type": "callback",
                    "text": "↩️Вернуться в главное меню",
                    "payload": "return_to_main_menu"
                }])
                
                keyboard = {
                    "type": "inline_keyboard",
                    "payload": {"buttons": buttons}
                }
                await send_message(user_id=user_id, text=report, attachments=[keyboard])

        elif payload == "confirm_reminders":
            await send_message(
                user_id=user_id,
                text="🔔 **Система умных напоминаний активна!**\n\nБот автоматически рассчитывает интервалы (за 30, 14, 7, 3, 1 дней и в день сдачи) в зависимости от сложности задачи.",
                attachments=[get_main_keyboard()]
            )

        elif payload == "confirm_open_profile":
            profile = await asyncio.to_thread(get_user_stats, user_id)
            
            current_exp = profile["exp"]
            current_coins = profile["coins"]
            streak_days = await asyncio.to_thread(get_user_streak, user_id)
            total_done = profile["tasks_done"]
            level = 1
            exp_need = 100
            temp_exp = current_exp
            
            while temp_exp > exp_need:
                temp_exp -= exp_need
                level += 1
                exp_need += 100
            profile_card_bytes = generate_profile_card(
                username="Пользователь",
                level=level,
                coins=current_coins,
                exp=current_exp,
                streak=streak_days,
                total_completed=total_done
            )

            await send_photo( 
                user_id=user_id,
                text="📊 Твой игровой профиль успешно загружен!",
                image_io=profile_card_bytes,  
                attachments=[get_main_keyboard()]
            )
            return

        elif payload.startswith("done_"):
            try:
                task_id = int(payload.split("_")[1])
                
                with sqlite3.connect(DB_TASKS) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT task_type, task_name FROM tasks WHERE id = ?", (task_id,))
                    task = cursor.fetchone()
                
                if task:
                    t_type, t_name = task

                    if "Обычное задание" in t_type:
                        exp, coins = 10, 5
                    elif "Олимпиада или конкурс" in t_type:
                        exp, coins = 30, 15
                    else:
                        exp, coins = 50, 30
                        
                    await asyncio.to_thread(update_user_info, user_id, exp=exp, coins=coins, task_done=True)
                    profile = await asyncio.to_thread(get_user_exp_coins, user_id)
                    await asyncio.to_thread(delete_task, task_id, user_id)

                    reward_message = (
                        f"🎉 Задание отмечено как выполненное и удалено из списка!\n"
                        f"Ты закрыл {t_name}\n"
                        f"🏆 Твоя награда: +{exp} EXP и +{coins} монет 🪙\n"
                        f"✨ Всего опыта: {profile['exp']} EXP\n"
                        f"💰 Баланс монет: {profile['coins']} монет🪙\n\n"
                        f"💕 Так держать, прокачивайся дальше "
                    )

                    await send_message(user_id=user_id, text=reward_message, attachments=[get_main_keyboard()])
                return
            except Exception:
                logger.exception("Ошибка при удалении задания")

        elif payload.startswith("cal_nav_"):
            _, _, y, m = payload.split('_')
            
            state_data = user_states.get(user_id)
            if not state_data or state_data.get("state") != "waiting_date":
                await send_message(user_id=user_id, text="Сессия истекла. Начни заново: /start", attachments=[get_main_keyboard()])
                return

            new_keyboard = get_calendar_keyboard(int(m), int(y))  
            callback_id = callback.get("callback_id")

            if callback_id:
                await answer_callback(
                    callback_id=callback_id,
                    text="Выбери дату",
                    attachments=new_keyboard
                )
            else:
                await send_message(user_id=user_id, text="Выбери дату", attachments=new_keyboard)
            return
        
        elif payload.startswith("cal_day_"):
            _, _, date_split = payload.split('_')
            y, m, d = date_split.split('-')
            date = d + "." + m + "." + y
            
            state_data = user_states.get(user_id)
            
            if not state_data or state_data.get("state") != "waiting_date":
                await send_message(user_id=user_id, text="Сессия истекла. Начни заново: /start", attachments=[get_main_keyboard()])
                return

            logger.info(f"Сохранение задачи: user_id={user_id}, chat_id={chat_id}")
            await asyncio.to_thread(
                save_task, 
                user_id, chat_id, state_data["task_type"], state_data["task_name"], date
            )
            user_states.pop(user_id, None)

            await send_message(
                user_id=user_id,
                text=f"Задание успешно сохранено!\n\n📌 Тип: {state_data['task_type']}\n📝 Название: {state_data['task_name']}\n📅 Дата дедлайна: {date}\n\nВыбери действие:",
                attachments=[get_main_keyboard()]
            )
            return

        elif payload in ("first_type", "second_type", "third_type"):
            types = {
                "first_type": "🟦Обычное задание",
                "second_type": "🟩Олимпиада или конкурс",
                "third_type": "🟪Проект или исследовательская работа",
            }
            user_states[user_id] = {"state": "waiting_name", "task_type": types[payload]}
            await send_message(user_id=user_id, text="Введи название задания:")
            
        elif payload == "return_to_main_menu":
            user_states.pop(user_id, None)
            menu_text = (
                "📋Главное меню функций\n\n"
                " Выбери, что ты хочешь сделать: \n"
                "➕ Добавить задачу - внести новое задание или проект\n"
                "📊 Моя нагрузка - посмотреть список текущих заданий и отменить их\n"
                "🔔 Напоминания - проверить статус работы напоминаний"
            )
            await send_message(user_id=user_id, text=menu_text, attachments=[get_main_keyboard()])
            return

        elif payload == "how_to_get_coins":
            text = (

            )
        


async def main():
    init_db()
    init_users_db()
    create_shop_tasks()
    init_shop()
    
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