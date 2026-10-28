from maxapi import Router
from maxapi.filters.callback_payload import CallbackPayload

from keyboards import get_main_keyboard

router = Router()

@router.message_callback(CallbackPayload.filter(data="confirm_watch_tasks"))
async def tasks_screen(event: CallbackPayload):
    await event.message.answer("экран находится в разработке :)")
    await event.message.answer("Выбери действие:", keyboard=get_main_keyboard())