from datetime import datetime

from maxapi import Router, F
from maxapi.types import MessageCreated
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.context import MemoryContext

from keyboards import get_main_keyboard, get_types_keyboard
from states import Form


router = Router()

@router.message_callback(CallbackPayload.filter(data="confirm_add_task"))  #ответ на добавление задания
async def ask_type(event: CallbackPayload):
    await event.message.answer("Выбери тип задания:", keyboard=get_types_keyboard())

@router.message_callback(
    (CallbackPayload.filter(data="first_type")) | 
    (CallbackPayload.filter(data="second_type")) |
    (CallbackPayload.filter(data="third_type"))
)
async def ask_name(event: CallbackPayload, context: MemoryContext):
    await context.update_data(task_type=event.data)
    await context.set_state(Form.name)
    await event.message.answer('Введи название задания, например "математика, №145":')

@router.message_created(F.message.body.text, Form.name)
async def ask_date(event: MessageCreated, context: MemoryContext):
    await context.update_data(task_name=event.message.body.text)
    await context.set_state(Form.date)
    await event.message.answer("Введи дату задания в виде ДД.ММ.ГГГГ:")
    
@router.message_created(F.message.body.text, Form.date)
async def save_task(event: MessageCreated, context: MemoryContext):
    date = event.message.body.text
    try:
        datetime.strptime(date, "%d.%m.%y")
    except ValueError:
        await event.message.answer("Неверный формат. Введи как 08.11.2026")
        return
    
    await context.update_data(task_date=date)
    data = await context.get_data()
    #  здесь задание записывается куда-то, пока непонятно куда
    
    await context.clear()
    await event.message.answer(
        "Задание сохранено!\n\nВыбери действие:",
        keyboard=get_main_keyboard()
    )