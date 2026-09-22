from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import signals
from ai_engine import test_ai
from database import db
from keyboards import (
    admin_menu_kb,
    admins_kb,
    ai_provider_kb,
    back_kb,
    cancel_kb,
    interval_kb,
    pairs_kb,
    pending_kb,
    settings_kb,
    signals_kb,
)
from texts import active_message, banned_message, broadcast_text

router = Router()


class AdminStates(StatesGroup):
    wait_setting = State()
    wait_broadcast = State()
    wait_pair = State()
    wait_admin_add = State()


async def _panel_text():
    c = await db.counts()
    total = sum(c.values())
    try:
        import json

        last = json.loads(await db.get_setting("last_signal", "{}") or "{}")
    except Exception:
        last = {}
    last_txt = "—"
    if last:
        emoji = "🟢 UP" if last.get("signal") == "UP" else "🔴 DOWN"
        last_txt = f"{last.get('ts')} · {emoji} · {last.get('confidence')}%"
    from ai_engine import provider_label

    pair = await db.get_setting("pair", "BTCUSDT")
    interval = await db.get_int("interval", 60)
    auto = await db.get_int("autosignals", 0)
    return (
        f"👑 <b>Админ-панель • PRO SIGNALS</b>\n\n"
        f"📊 <b>Статистика</b>\n"
        f"👥 Всего: <b>{total}</b> · ✅ Активных: <b>{c['active']}</b>\n"
        f"⏳ В ожидании: <b>{c['pending']}</b> · 🚫 Отклонено: <b>{c['banned']}</b>\n\n"
        f"📡 <b>Сигналы</b>\n"
        f"Статус: {'ВКЛ ✅' if auto else 'ВЫКЛ ⛔'} · Пара: <b>{pair}</b> · {interval}с\n"
        f"AI: <b>{await provider_label(db)}</b>\n"
        f"🕓 Последний: {last_txt}"
    )


async def _is_admin_filter(user_id) -> bool:
    return await db.is_admin(user_id)


@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if not await _is_admin_filter(msg.from_user.id):
        return
    await msg.answer(await _panel_text(), reply_markup=admin_menu_kb())


@router.callback_query(F.data == "adm:menu")
async def adm_back_menu(cb: CallbackQuery):
    await cb.message.edit_text(await _panel_text(), reply_markup=admin_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:refresh")
async def adm_refresh(cb: CallbackQuery):
    await adm_back_menu(cb)


@router.callback_query(F.data == "adm:pending")
async def adm_pending(cb: CallbackQuery):
    pend = await db.users_by_status("pending", 20)
    if not pend:
        await cb.message.edit_text("Нет ожидающих заявок ✅", reply_markup=back_kb())
        await cb.answer()
        return
    lines = [f"📥 <b>Новые заявки: {len(pend)}</b>\n"]
    for i, u in enumerate(pend, 1):
        name = (u.get("full_name") or u.get("username") or str(u["telegram_id"]))[:18]
        lines.append(
            f"{i}. 👤 <b>{name}</b> (@{u.get('username') or '—'})\n"
            f"   💼 PO: <code>{u.get('po_id') or '—'}</code> · TG: <code>{u['telegram_id']}</code>"
        )
    await cb.message.edit_text("\n".join(lines), reply_markup=pending_kb(pend))
    await cb.answer()


@router.callback_query(F.data == "adm:stats")
async def adm_stats(cb: CallbackQuery):
    from signals import stats_text

    await cb.message.edit_text(await stats_text(db, cb.from_user.id), reply_markup=back_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:settings")
async def adm_settings(cb: CallbackQuery):
    await cb.message.edit_text(
        await signals.default_settings_text(db), reply_markup=settings_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "adm:signals")
async def adm_signals(cb: CallbackQuery):
    await cb.message.edit_text(
        await signals.signals_screen_text(db), reply_markup=signals_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "adm:bcast")
async def adm_bcast(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.wait_broadcast)
    await cb.message.answer(
        "📣 Введите текст рассылки — уйдёт всем <b>активированным</b> юзерам:",
        reply_markup=cancel_kb(),
    )
    await cb.answer()


@router.message(AdminStates.wait_broadcast, F.text)
async def do_broadcast(msg: Message, state: FSMContext):
    ids = await db.active_tg_ids()
    count = 0
    text = broadcast_text(msg.text)
    for tg in ids:
        try:
            await msg.bot.send_message(tg, text)
            count += 1
        except Exception:
            continue
    await state.clear()
    await msg.answer(f"✅ Рассылка отправлена <b>{count}</b> юзерам.")


# ---------------- approve / reject ----------------

async def _approve_or_reject(cb: CallbackQuery, approve: bool):
    tg = int(cb.data.split(":", 1)[1])
    await cb.answer()
    user = await db.get_user(tg)
    if not user:
        await cb.message.edit_text("Юзер не найден.", reply_markup=back_kb())
        return
    if user["status"] == "active":
        await cb.message.edit_text(
            f"ℹ️ Юзер <code>{tg}</code> уже активирован.", reply_markup=back_kb()
        )
        return
    if approve:
        await db.set_user(tg, status="active", activated_at=db.now())
        pair = await db.get_setting("pair", "BTCUSDT")
        interval = await db.get_int("interval", 60)
        from ai_engine import provider_label

        label = await provider_label(db)
        try:
            await cb.bot.send_message(tg, active_message(pair, interval, label))
        except Exception:
            pass
        name = (user.get("full_name") or user.get("username") or str(tg))[:18]
        await cb.message.edit_text(
            f"✅ <b>{name}</b> (<code>{tg}</code>) активирован.\n"
            f"Пользователю отправлено уведомление.",
            reply_markup=back_kb(),
        )
    else:
        await db.set_user(tg, status="banned", po_id=user.get("po_id"))
        contact = await db.get_setting("admin_contact")
        try:
            await cb.bot.send_message(tg, banned_message(contact))
        except Exception:
            pass
        await cb.message.edit_text(
            f"🚫 Юзер <code>{tg}</code> отклонён (заблокирован).",
            reply_markup=back_kb(),
        )


@router.callback_query(F.data.startswith("apv:"))
async def approve_user(cb: CallbackQuery):
    await _approve_or_reject(cb, True)


@router.callback_query(F.data.startswith("rej:"))
async def reject_user(cb: CallbackQuery):
    await _approve_or_reject(cb, False)


# ---------------- settings values ----------------

async def _label_for_key(key):
    return {
        "referral_link": "Реф. ссылка",
        "promo_code": "Промокод",
        "admin_contact": "Контакт (юзернейм без @)",
        "min_deposit": "Мин. депозит ($)",
        "openai_key": "AI API Key",
        "openai_model": "AI Модель",
        "openai_base": "AI Base URL",
    }.get(key, key)


@router.callback_query(F.data.startswith("set:"))
async def adm_set_start(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":", 1)[1]
    await state.set_state(AdminStates.wait_setting)
    await state.update_data(set_key=key)
    await cb.message.answer(
        f"✏️ Отправь новое значение для «<b>{await _label_for_key(key)}</b>»:",
        reply_markup=cancel_kb(),
    )
    await cb.answer()


@router.message(AdminStates.wait_setting, F.text)
async def adm_set_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("set_key")
    value = msg.text.strip()
    if key == "min_deposit":
        if not value.isdigit() or int(value) < 1:
            await msg.answer("⚠️ Введи число от 1 и больше.")
            return
    if key == "admin_contact":
        value = value.lstrip("@")
    await db.set_setting(key, value)
    await state.clear()
    await msg.answer(
        f"✅ «{await _label_for_key(key)}» сохранён.",
        reply_markup=back_kb(),
    )


# ---------------- signals ----------------

@router.callback_query(F.data == "sig:toggle")
async def sig_toggle(cb: CallbackQuery):
    cur = await db.get_int("autosignals", 0)
    await db.set_setting("autosignals", "0" if cur else "1")
    await cb.message.edit_text(
        await signals.signals_screen_text(db), reply_markup=signals_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "sig:force")
async def sig_force(cb: CallbackQuery):
    await cb.answer("⏳ Генерирую сигнал...")
    owner = config.OWNER_ID
    active = await db.active_tg_ids()
    admins = await db.admin_ids()
    targets = list(dict.fromkeys(active + admins + ([owner] if owner else [])))
    if not targets:
        targets = [cb.from_user.id]
    data = await signals.bus.push(targets)
    if data is None:
        await cb.message.answer("⛔ Сигнал уже генерируется — подожди секунду.")
        return
    emoji = "🟢 UP" if data["signal"] == "UP" else "🔴 DOWN"
    await cb.message.answer(
        f"📡 Сигнал отправлен: <b>{emoji}</b> ({data['confidence']}%) → {len(targets)} получателей."
    )


@router.callback_query(F.data == "sig:test")
async def sig_test(cb: CallbackQuery):
    await cb.answer("🧪 Тестирую...")
    pair = await db.get_setting("pair", "BTCUSDT")
    try:
        ok, text = await test_ai(db, pair)
    except Exception as exc:
        ok, text = False, f"Ошибка: {exc}"
    await cb.message.answer(
        ("✅ " if ok else "⚠️ ") + text, reply_markup=back_kb()
    )


@router.callback_query(F.data == "sig:pairs")
async def sig_pairs(cb: CallbackQuery):
    await cb.message.edit_text("📈 <b>Выбери пару:</b>", reply_markup=pairs_kb())
    await cb.answer()


@router.callback_query(F.data == "sig:ints")
async def sig_ints(cb: CallbackQuery):
    await cb.message.edit_text("⏱ <b>Интервал сигналов:</b>", reply_markup=interval_kb())
    await cb.answer()


@router.callback_query(F.data == "sig:ai")
async def sig_ai(cb: CallbackQuery):
    cur = await db.get_setting("ai_provider", "strategy")
    await cb.message.edit_text("🤖 <b>AI-провайдер сигналов:</b>", reply_markup=ai_provider_kb(cur))
    await cb.answer()


@router.callback_query(F.data.startswith("ai:"))
async def sig_ai_set(cb: CallbackQuery, state: FSMContext):
    provider = cb.data.split(":", 1)[1]
    await db.set_setting("ai_provider", provider)
    await state.clear()
    await cb.message.edit_text(
        await signals.signals_screen_text(db), reply_markup=signals_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "sig:pair_custom")
async def sig_pair_custom(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.wait_pair)
    await cb.message.answer(
        "✏️ Напиши пару, например <code>BTCUSDT</code> или <code>ETHUSDT</code>:",
        reply_markup=cancel_kb(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("sig:pair:"))
async def sig_pair_set(cb: CallbackQuery):
    pair = cb.data.split(":", 2)[2]
    await db.set_setting("pair", pair)
    await cb.message.edit_text(
        await signals.signals_screen_text(db), reply_markup=signals_kb()
    )
    await cb.answer()


@router.message(AdminStates.wait_pair, F.text)
async def sig_pair_save(msg: Message, state: FSMContext):
    pair = msg.text.strip().upper().replace(" ", "")
    if not re_full_pair(pair):
        await msg.answer("⚠️ Формат пары: <code>BTCUSDT</code> (валютная пара).")
        return
    await db.set_setting("pair", pair)
    await state.clear()
    from keyboards import signals_kb

    await msg.answer(
        f"✅ Пара сохранена: <b>{pair}</b>", reply_markup=back_kb()
    )


def re_full_pair(pair):
    import re

    return bool(re.fullmatch(r"[A-Z0-9]{6,12}", pair))


@router.callback_query(F.data.startswith("sig:int:"))
async def sig_int_set(cb: CallbackQuery):
    interval = int(cb.data.split(":", 2)[2])
    await db.set_setting("interval", interval)
    await cb.message.edit_text(
        await signals.signals_screen_text(db), reply_markup=signals_kb()
    )
    await cb.answer()


# ---------------- admins ----------------

@router.callback_query(F.data == "adm:admins")
async def adm_admins(cb: CallbackQuery):
    added = await db.admin_ids()
    is_owner = config.OWNER_ID == cb.from_user.id
    await cb.message.edit_text(await signals.admins_text(db), reply_markup=admins_kb(added, is_owner))
    await cb.answer()


@router.callback_query(F.data == "adm:add")
async def adm_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.wait_admin_add)
    await cb.message.answer(
        "➕ Пришли <b>numeric Telegram ID</b> нового админа "
        "(узнать: у него бот @userinfobot или /start в панели):",
        reply_markup=cancel_kb(),
    )
    await cb.answer()


@router.message(AdminStates.wait_admin_add, F.text)
async def adm_add_save(msg: Message, state: FSMContext):
    raw = msg.text.strip()
    if not raw.isdigit():
        await msg.answer("⚠️ Telegram ID — число. Пример: <code>123456789</code>.")
        return
    new_id = int(raw)
    await db.add_admin(new_id, msg.from_user.id)
    await state.clear()
    await msg.answer(f"✅ Админ <code>{new_id}</code> добавлен. Он увидит /admin.")


@router.callback_query(F.data.startswith("admdel:"))
async def adm_del(cb: CallbackQuery):
    if cb.from_user.id != config.OWNER_ID:
        await cb.answer("Только владелец может удалять админов.", show_alert=True)
        return
    tg = int(cb.data.split(":", 1)[1])
    if tg == config.OWNER_ID:
        await cb.answer("Нельзя удалить владельца.", show_alert=True)
        return
    await db.remove_admin(tg)
    added = await db.admin_ids()
    await cb.message.edit_text(
        await signals.admins_text(db), reply_markup=admins_kb(added, True)
    )
    await cb.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Отменено")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass