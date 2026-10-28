from maxapi import Router
from maxapi.types import BotStarted, Command, MessageCreated
from maxapi.context import MemoryContext

from keyboards import get_main_keyboard

router = Router()

# Ответ бота при нажатии на кнопку "Начать"
@router.bot_started()
async def bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Отправь мне /start'
    )

# Ответ бота на команду /start
@router.message_created(Command('start'))  # первый экран
async def main_screen(event: MessageCreated, context: MemoryContext):
    await context.clear()
    await event.message.answer("Выбери действие:", keyboard=get_main_keyboard())