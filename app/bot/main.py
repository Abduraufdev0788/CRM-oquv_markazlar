from aiogram import Bot, Dispatcher
from app.config import settings
from app.bot.handlers import router

async def start_bot():
    if not settings.TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set in .env")
        return

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    print("Bot is starting...")
    await dp.start_polling(bot)
