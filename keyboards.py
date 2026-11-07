import calendar
from datetime import datetime

def get_main_keyboard():
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [
                    {
                        "type": "callback",
                        "text": "➕ Добавить задание",
                        "payload": "confirm_add_task",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "📊 Нагрузка",
                        "payload": "confirm_watch_tasks",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "🔔 Напоминания",
                        "payload": "confirm_reminders",
                    }
                ],
                [
                    {
                        "type":"callback",
                        "text": "👤 Профиль",
                        "payload":"confirm_open_profile" 
                    }
                ],
                [
                    {
                        "type":"callback",
                        "text": "🏪 Магазин",
                        "payload":"confirm_open_shop" 
                    }
                ]
            ]
        },
    }


def get_types_keyboard():
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [
                    {
                        "type": "callback",
                        "text": "🟦Обычное задание",
                        "payload": "first_type",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "🟩Олимпиада или конкурс",
                        "payload": "second_type",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "🟪Проект или исследовательская работа",
                        "payload": "third_type",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "↩️Вернуться в главное меню",
                        "payload": "return_to_main_menu"
                    }
                ]
            ]
        },
    }


def get_calendar_keyboard(month: int, year: int) -> list:
    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    month_title = f"{months[month - 1]} {year}"
    month_grid = calendar.monthcalendar(year, month)
    rows = []

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    nav_row = [
        {"type": "callback", "text": "◀", "payload": f"cal_nav_{prev_year}_{prev_month:02d}"},
        {"type": "callback", "text": month_title, "payload": "cal_ignore"}, # Кнопка-заголовок
        {"type": "callback", "text": "▶", "payload": f"cal_nav_{next_year}_{next_month:02d}"}
    ]
    rows.append(nav_row)

    weekdays_row = [
        {"type": "callback", "text": day, "payload": "cal_ignore"}
        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ]
    rows.append(weekdays_row)

    for week in month_grid:
        week_row = []
        for day in week:
            if day == 0:
                # Пустая ячейка (заглушка)
                week_row.append({"type": "callback", "text": "\u00A0", "payload": "cal_ignore"})
            else:
                # Кнопка с датой
                # payload: "cal_day_YYYY-MM-DD"
                date_str = f"{year}-{month:02d}-{day:02d}"
                week_row.append({
                    "type": "callback", 
                    "text": str(day), 
                    "payload": f"cal_day_{date_str}"
                })
        rows.append(week_row)

    main_menu = [
        {
            "type": "callback",
            "text": "↩️Вернуться в главное меню",
            "payload": "return_to_main_menu"
        }
    ]
    rows.append(main_menu)
    
    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": rows
            }
        }
    ]

def get_shop_keyboard(item_id, is_bought, is_equipped):
    buttons = []

    if not is_bought:
        buttons.append([{
            "type": "callback",
            "text": "🪙 Купить",
            "payload": f"shop_buy_{item_id}"
        }])

    elif not is_equipped:
        buttons.append([{
            "type": "callback",
            "text": "✅ Установить",
            "payload": f"shop_equip_{item_id}"
        }])

    else:
        buttons.append([{
            "type": "callback",
            "text": "✅ Установлена",
            "payload": "shop_current"
        }])

    buttons.append([
        {
            "type": "callback",
            "text": "◀️",
            "payload": "shop_prev"
        },
        {
            "type": "callback",
            "text": "▶️",
            "payload": "shop_next"
        }
    ])

    buttons.append([{
        "type": "callback",
        "text": "🪙 Как получать монеты?",
        "payload": "how_to_get_coins"
    }])

    buttons.append([{
        "type": "callback",
        "text": "↩️ Главное меню",
        "payload": "return_to_main_menu"
    }])

    return {
        "type": "inline_keyboard",
        "payload": {"buttons": buttons}
    }