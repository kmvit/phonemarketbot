import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from bot.handlers import user, admin
from db.utils import setup_db

async def main():
    setup_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрируем user.router первым, чтобы обработчики с StateFilter имели приоритет
    # Это важно для обработки ввода количества товара
    dp.include_router(user.router)
    dp.include_router(admin.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())