import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import handlers_admin
import handlers_user
import signals
from database import db


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger = logging.getLogger("main")

    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Скопируй .env.example в .env и заполни.")
        return
    if not config.OWNER_ID:
        logger.warning("OWNER_ID не задан — владелец не установлен, добавь админов через ADMIN_IDS или позже.")

    await db.init()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    signals.bus = signals.SignalBus(bot, db)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers_user.router)
    dp.include_router(handlers_admin.router)

    if config.OWNER_ID:
        try:
            await bot.send_message(
                config.OWNER_ID,
                "🟢 <b>Бот запущен.</b>\nПанель: /admin\n\n"
                "🚀 Не забудь: в панели включи «⏯ Вкл / Выкл авто-сигналы».",
            )
        except Exception:
            logger.warning("Не удалось отправить стартовое сообщение владельцу.")

    logger.info("Bot started, polling...")
    await bot.delete_webhook(drop_pending_updates=True)

    scheduler = asyncio.create_task(signals.signal_loop())
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.cancel()


if __name__ == "__main__":
    asyncio.run(main())