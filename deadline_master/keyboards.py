from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

def get_main_keyboard():
    return (
        InlineKeyboardBuilder()
        .callback("Добавить задание", "confirm_add_task")
        .callback("Нагрузка", "confirm_watch_tasks")
        .callback("Напоминания", "confirm_reminders")
        .adjust(1, 1)
    )

def get_types_keyboard():
    return (
        InlineKeyboardBuilder()
        .callback("Обычное задание", "first_type")
        .callback("Олимпиада или конкурс", "second_type")
        .callback("Проект или исследовательская работа", "third_type")
        .adjust(1, 1)
    )