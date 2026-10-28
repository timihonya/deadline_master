import asyncio
import logging

from maxapi import Bot, Dispatcher

from config import TOKEN
from handlers import start_router, add_new_task_router, watch_tasks_router

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp = Dispatcher()
dp.include_router(start_router)
dp.include_router(add_new_task_router)
dp.include_router(watch_tasks_router)

async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())