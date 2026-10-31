
def get_main_keyboard():
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [
                    {
                        "type": "callback",
                        "text": "Добавить задание",
                        "payload": "confirm_add_task",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "Нагрузка",
                        "payload": "confirm_watch_tasks",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "Напоминания",
                        "payload": "confirm_reminders",
                    }
                ],
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
                        "text": "Обычное задание",
                        "payload": "first_type",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "Олимпиада или конкурс",
                        "payload": "second_type",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "Проект или исследовательская работа",
                        "payload": "third_type",
                    }
                ],
            ]
        },
    }
