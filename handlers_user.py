import re

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import signals
from database import db
from keyboards import cancel_kb, welcome_kb

router = Router()


class UserStates(StatesGroup):
    wait_po_id = State()


RUS_LANGS = {"ru", "uk", "be"}


async def _ref_for(lang_code):
    if (lang_code or "").lower() in RUS_LANGS:
        return await db.get_setting("referral_link_ru")
    return await db.get_setting("referral_link_int")


async def ai_label():
    from ai_engine import provider_label

    return await provider_label(db)


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    tg = msg.from_user.id
    uname = msg.from_user.username or ""
    fname = (msg.from_user.full_name or "друг").strip() or str(tg)
    await db.upsert_user(tg, uname, fname)

    if await db.is_admin(tg):
        from texts import admin_hint

        await msg.answer(admin_hint())

    user = await db.get_user(tg)
    ref = await _ref_for(msg.from_user.language_code)
    promo = await db.get_setting("promo_code")
    contact = await db.get_setting("admin_contact")
    min_dep = await db.get_int("min_deposit", 10)

    if user["status"] == "active":
        pair = await db.get_setting("pair", "BTCUSDT")
        interval = await db.get_int("interval", 60)
        from texts import active_message

        await msg.answer(active_message(pair, interval, await ai_label()))
        return

    if user["status"] == "pending":
        from texts import pending_message

        await msg.answer(pending_message(user.get("po_id") or "—", contact))
        return

    if user["status"] == "banned":
        from texts import banned_message

        await msg.answer(banned_message(contact))
        return

    from texts import welcome

    await msg.answer(
        welcome(fname, ref, promo, contact, min_dep),
        reply_markup=welcome_kb(contact),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "sybid")
async def cb_send_id(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(UserStates.wait_po_id)
    from texts import ASK_PO_ID

    await cb.message.answer(ASK_PO_ID, reply_markup=cancel_kb())


@router.callback_query(F.data == "po_help")
async def cb_po_help(cb: CallbackQuery):
    await cb.answer()
    from texts import PO_HELP

    await cb.message.answer(PO_HELP)


@router.callback_query(F.data == "contact")
async def cb_contact(cb: CallbackQuery):
    contact = await db.get_setting("admin_contact")
    await cb.answer()
    if contact:
        await cb.message.answer(
            f"💬 Пиши сюда: <a href='https://t.me/{contact}'>@{contact}</a>\n"
            f"Укажи свой Telegram ID и Pocket ID — активируем быстрее."
        )
    else:
        await cb.message.answer("Контакт ещё не задан админом.")


@router.message(UserStates.wait_po_id, F.text)
async def got_po_id(msg: Message, state: FSMContext):
    raw = msg.text.strip()
    if not re.fullmatch(r"\d{4,12}", raw):
        await msg.answer(
            "⚠️ ID выглядит как число (4–12 цифр). Проверь, пожалуйста.\n"
            "Pocket Option → аватар → Личный кабинет → ID."
        )
        return
    await state.clear()
    tg = msg.from_user.id
    await db.set_user(tg, po_id=raw, status="pending")
    user = await db.get_user(tg)

    from texts import RECEIVED_PO_ID

    await msg.answer(RECEIVED_PO_ID(raw))

    await _notify_admins(msg.bot, user)


@router.message(F.text.regexp(r"^\d{4,12}$"))
async def direct_po_id(msg: Message):
    tg = msg.from_user.id
    user = await db.get_user(tg)
    if user and user["status"] in ("new", "pending"):
        raw = msg.text.strip()
        await db.set_user(tg, po_id=raw, status="pending")
        user = await db.get_user(tg)
        from texts import RECEIVED_PO_ID

        await msg.answer(RECEIVED_PO_ID(raw))
        await _notify_admins(msg.bot, user)


@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Отменено")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def _notify_admins(bot, user):
    from keyboards import approve_kb

    owner = config.OWNER_ID
    ids = await db.admin_ids()
    targets = list(dict.fromkeys(([owner] if owner else []) + ids))
    text = (
        f"🆕 <b>Новая заявка на активацию!</b>\n\n"
        f"👤 {user.get('full_name') or '—'} (@{user.get('username') or '—'})\n"
        f"🆔 Telegram: <code>{user['telegram_id']}</code>\n"
        f"💼 Pocket ID: <code>{user.get('po_id') or '—'}</code>\n"
        f"🕐 {user.get('created_at')}\n\n"
        f"Проверил депозит от $"
        f"{await db.get_int('min_deposit', 10)} — подтверждай ✅"
    )
    for tid in targets:
        try:
            await bot.send_message(tid, text, reply_markup=approve_kb(user["telegram_id"]))
        except Exception:
            continue