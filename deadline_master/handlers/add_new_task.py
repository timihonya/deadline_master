from maxapi import Router, F
from maxapi.types import MessageCreated
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.context import MemoryContext

from keyboards import get_main_keyboard, get_types_keyboard
from states import Form


router = Router()

@router.message_callback(CallbackPayload.filter(data="confirm_add_task"))  #ответ на добавление задания
async def on_confirm_add_task(event: CallbackPayload):  # потом изменю названия
    await event.message.answer("выберите тип задания:", keyboard=get_types_keyboard())

@router.message_callback(
    (CallbackPayload.filter(data="first_type")) | 
    (CallbackPayload.filter(data="second_type")) |
    (CallbackPayload.filter(data="third_type"))
)
async def new_task_type(event: CallbackPayload, context: MemoryContext):
    await context.update_data(task_type=event.data)
    await context.set_state(Form.name)
    await event.message.answer('введите название задания, например "математика, №145"')

@router.message_created(F.message.body.text, Form.name)
async def new_task_name(event: MessageCreated, context: MemoryContext):
    await context.update_data(task_name=event.message.body.text)
    await context.set_state(Form.date)
    await event.message.answer("введите дату задания в виде ДД.ММ.ГГГГ")  # желательно потом сделать что-то типа календаря для защиты от недалёких
    
@router.message_created(F.message.body.text, Form.date)
async def new_task_date(event: MessageCreated, context: MemoryContext):
    #  тут должна идти проверка на правильность, сделаем её чуть позже
    await context.update_data(task_date=event.message.body.text)
    data = await context.get_data()
    #  здесь задание записывается куда-то, пока непонятно куда
    
    await context.clear()
    await event.message.answer(
        "Задание сохранено!\n\nВыбери действие:",
        keyboard=get_main_keyboard()
    )