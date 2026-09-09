"""Главный файл бота. Запуск: python bot.py (long-polling, без вебхука)."""
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import funnel
from database import Database
from keyboards import (
    start_keyboard,
    funnel_question_keyboard,
    final_keyboard,
    video_keyboard,
    instruction_keyboard,
    admin_keyboard,
    admin_settings_keyboard,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db = Database(config.DATA_PATH)

# Поля, которые админ редактирует текстом (ключ callback -> ключ в настройках)
EDIT_FIELDS = {
    "edit_ref": "referral_link",
    "edit_promo": "promo_code",
    "edit_channel": "private_channel_link",
    "edit_instruction": "instructions",
}


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# =================== СТАРТ ===================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.update_user(
        user.id,
        username=user.username,
        first_name=user.first_name,
        step="start",
    )
    s = await db.get_settings()
    text = (
        f"{s.get('welcome_text', '')}\n\n"
        "Мы поможем тебе пройти быструю квалификацию и получить доступ "
        "к трейдинг-стратегиям.\n\nДавай начнём 👇"
    )
    await message.answer(text, reply_markup=start_keyboard())


# =================== ВОРОНКА ===================
@dp.callback_query(F.data == "start_funnel")
async def start_funnel(call: CallbackQuery):
    user_id = call.from_user.id
    await db.update_user(user_id, step="started", funnel_done=False)
    first = funnel.FUNNEL_STEPS[0]
    kb = funnel_question_keyboard(first["key"], first["options"])
    try:
        await call.message.edit_text(f"<b>{first['question']}</b>", reply_markup=kb)
    except Exception:
        await call.message.answer(f"<b>{first['question']}</b>", reply_markup=kb)


@dp.callback_query(F.data.startswith("funnel_"))
async def on_funnel_answer(call: CallbackQuery):
    await funnel.process_funnel_answer(call, db)


# =================== ФИНАЛ ВОРОНКИ ===================
@dp.callback_query(F.data == "show_video")
async def show_video(call: CallbackQuery):
    s = await db.get_settings()
    video_id = s.get("video_guide_id")
    if not video_id:
        await call.answer("Видео пока не загружено админом", show_alert=True)
        return
    try:
        await call.message.answer_video(
            video=video_id,
            caption="🎬 <b>Видео-гайд по регистрации</b>",
            reply_markup=video_keyboard(),
        )
    except Exception as e:
        logger.error("Ошибка отправки видео: %s", e)
        await call.answer("Ошибка отправки видео", show_alert=True)


@dp.callback_query(F.data == "show_instruction")
async def show_instruction(call: CallbackQuery):
    s = await db.get_settings()
    text = (
        f"📝 <b>Инструкция по регистрации</b>\n\n"
        f"{s.get('instructions', '')}\n\n"
        f"🔗 Ссылка: {s.get('referral_link', '')}\n"
        f"🎁 Промокод: <code>{s.get('promo_code', '')}</code>\n"
        f"📢 Канал: {s.get('private_channel_link', '')}"
    )
    await call.message.answer(text, reply_markup=instruction_keyboard())


# =================== АДМИН: ПАНЕЛЬ ===================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return
    await message.answer("⚙️ <b>Админ-меню</b>", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    total = await db.users_count()
    completed = await db.completed_count()
    users = await db.all_users()
    avg = len([u for u in users if u.get("step") == "completed"])
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Юзеров всего: <b>{total}</b>\n"
        f"✅ Прошли воронку: <b>{completed}</b>\n"
        f"🏁 Получили результат: <b>{avg}</b>"
    )
    await call.message.answer(text)


@dp.callback_query(F.data == "admin_settings")
async def admin_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите, что хотите изменить. Текст нового значения отправьте следующим сообщением.",
        reply_markup=admin_settings_keyboard(),
    )


@dp.callback_query(F.data == "admin_settings_back")
async def admin_settings_back(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await admin_panel(call.message)


# Редактирование поля
@dp.callback_query(F.data.in_(EDIT_FIELDS.keys()))
async def edit_field_start(call: CallbackQuery):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return
    field = EDIT_FIELDS[call.data]
    await db.update_user(user_id, admin_edit=field)
    labels = {
        "referral_link": "🔗 пришлите новую реф-ссылку",
        "promo_code": "🎁 пришлите новый промокод",
        "private_channel_link": "📢 пришлите новую ссылку на канал",
        "instructions": "📝 пришлите новый текст инструкции",
    }
    await call.message.answer(f"Ок, {labels[field]}:")


@dp.callback_query(F.data == "show_current")
async def show_current(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    s = await db.get_settings()
    text = (
        "📋 <b>Текущие настройки</b>\n\n"
        f"🔗 Реф-ссылка:\n<code>{s.get('referral_link', '')}</code>\n\n"
        f"🎁 Промокод: <code>{s.get('promo_code', '')}</code>\n\n"
        f"📢 Канал: {s.get('private_channel_link', '')}\n\n"
        f"🎬 Видео: {'загружено ✅' if s.get('video_guide_id') else 'не загружено ❌'}\n\n"
        f"📝 Инструкция:\n{s.get('instructions', '')}"
    )
    await call.message.answer(text, reply_markup=admin_settings_keyboard())


@dp.callback_query(F.data == "admin_upload_video")
async def admin_upload_video(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer("📤 Отправьте видео-файл (mp4, до 50MB) — оно станет видео-гайдом.")


@dp.callback_query(F.data == "admin_reset_user")
async def admin_reset(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.answer("⛔ Для сброса используйте команду /reset <user_id>")


# Приём нового значения от админа (когда он редактирует поле)
@dp.message(F.text)
async def on_admin_text(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id) or message.text.startswith("/"):
        return
    user = await db.get_user(user_id)
    field = (user or {}).get("admin_edit")
    if not field:
        return
    await db.update_setting(field, message.text)
    await db.update_user(user_id, admin_edit=None)
    await message.answer("✅ Сохранено!")


# Загрузка видео от админа
@dp.message(F.video)
async def on_video_upload(message: Message):
    if not is_admin(message.from_user.id):
        return
    video_id = message.video.file_id
    await db.update_setting("video_guide_id", video_id)
    await message.answer(f"✅ Видео-гайд сохранён!\nID: <code>{video_id}</code>")


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /reset <user_id>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Неверный id")
        return
    if await db.user_exists(uid):
        await db.update_user(uid, step=None, funnel_done=False)
        await message.answer(f"✅ Прогресс юзера {uid} сброшен")
    else:
        await message.answer("Юзер не найден")


# =================== ЗАПУСК ===================
async def main():
    if not config.BOT_TOKEN:
        logger.error("Не задан BOT_TOKEN в .env")
        return
    await db.connect()
    logger.info("Локальная БД готова: %s", config.DATA_PATH)
    logger.info("Бот запущен (long polling, без вебхука)...")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")