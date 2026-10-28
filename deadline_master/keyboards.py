from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

def get_main_keyboard():
    return (
        InlineKeyboardBuilder()
        .callback("Добавить задание", "confirm_add_task")
        .callback("Нагрузка", "confirm_watch_tasks")
        .callback("что-то", "confirm_smth")
        .adjust(1, 1)
    )

def get_types_keyboard():
    return (
        InlineKeyboardBuilder()
        .callback("1", "first_type")
        .callback("2", "second_type")
        .callback("3", "third_type")
        .adjust(1, 1)
    )