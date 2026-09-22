import asyncio
import json
import logging
from datetime import timedelta

from ai_engine import generate_signal, provider_label
from market import exchange_symbol, get_candles
from texts import msk_now, signal_text

log = logging.getLogger("signals")

bus = None


class SignalBus:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.lock = asyncio.Lock()
        self.last = None

    async def build(self, pair=None):
        pair = pair or await self.db.get_setting("pair", "BTC/USD")
        interval = await self.db.get_int("interval", 60)
        exc = exchange_symbol(pair)
        candles = await get_candles(exc)
        sig = await generate_signal(self.db, pair, candles)
        now = msk_now()
        return {
            "pair": pair,
            "interval": interval,
            "signal": sig["signal"],
            "confidence": sig["confidence"],
            "reason": sig["reason"],
            "source": sig["source"],
            "ts": now.strftime("%d.%m %H:%M:%S"),
            "ts_dt": now,
            "exp": now + timedelta(seconds=interval),
        }

    async def push(self, target_ids):
        if self.lock.locked():
            return None
        async with self.lock:
            data = await self.build()
            self.last = data
            await self.db.set_setting(
                "last_signal",
                json.dumps(
                    {
                        "pair": data["pair"],
                        "signal": data["signal"],
                        "confidence": data["confidence"],
                        "source": data["source"],
                        "ts": data["ts"],
                    },
                    ensure_ascii=False,
                ),
            )
            text = signal_text(data)
            for tg in target_ids:
                try:
                    await self.bot.send_message(tg, text)
                except Exception:
                    continue
            return data

    async def tick(self):
        if not await self.db.get_int("autosignals", 0):
            return
        ids = await self.db.active_tg_ids()
        if not ids:
            return
        await self.push(ids)


async def signal_loop():
    from database import db

    while True:
        try:
            await bus.tick()
        except Exception as exc:
            log.warning("signal tick error: %s", exc)
        interval = await db.get_int("interval", 60)
        await asyncio.sleep(max(interval, 30))


async def default_settings_text(db):
    return (
        f"⚙️ <b>Настройки</b>\n\n"
        f"🇷🇺 Реф. (РФ):\n{await db.get_setting('referral_link_ru')}\n"
        f"🌍 Реф. (INT):\n{await db.get_setting('referral_link_int')}\n"
        f"🎁 Промокод: <b>{await db.get_setting('promo_code')}</b>\n"
        f"👤 Контакт: @{await db.get_setting('admin_contact') or 'не задан'}\n"
        f"💰 Мин. депозит: <b>${await db.get_int('min_deposit', 10)}</b>\n"
        f"🤖 Модель: <b>{await provider_label(db)}</b>"
    )


async def signals_screen_text(db):
    pair = await db.get_setting("pair", "BTCUSDT")
    interval = await db.get_int("interval", 60)
    auto = await db.get_int("autosignals", 0)
    status = "ВКЛ ✅" if auto else "ВЫКЛ ⛔"
    try:
        last = json.loads(await db.get_setting("last_signal", "{}") or "{}")
    except json.JSONDecodeError:
        last = {}
    last_txt = "—"
    if last:
        emoji = "🟢 UP" if last.get("signal") == "UP" else "🔴 DOWN"
        last_txt = f"{last.get('ts')} · {emoji} · {last.get('confidence')}%"
    return (
        f"📡 <b>Сигналы</b>\n\n"
        f"Авто-сигналы: <b>{status}</b>\n"
        f"Пара: <b>{pair}</b>\n"
        f"Интервал: <b>{interval} сек</b>\n"
        f"AI: <b>{await provider_label(db)}</b>\n"
        f"🕓 Последний сигнал: {last_txt}"
    )


async def admins_text(db):
    owner = 0
    try:
        import config

        owner = config.OWNER_ID
    except Exception:
        pass
    added = await db.admin_ids()
    lines = ["👥 <b>Админы</b>\n"]
    if owner:
        lines.append(f"👑 Владелец: <code>{owner}</code>")
    others = [a for a in added if a != owner]
    if others:
        lines.append("➕ Добавленные:")
        for a in others:
            lines.append(f"  • <code>{a}</code>")
    else:
        lines.append("➕ Добавленные: нет")
    return "\n".join(lines)


async def stats_text(db, user_id):
    c = await db.counts()
    total = sum(c.values())
    last_users = await db.recent_users(8)
    st_emoji = {
        "new": "🆕",
        "pending": "⏳",
        "active": "✅",
        "banned": "🚫",
    }
    rows = []
    for u in last_users:
        name = (u.get("full_name") or u.get("username") or str(u["telegram_id"]))[:18]
        rows.append(
            f"{st_emoji.get(u['status'], '?')} <b>{name}</b> · "
            f"{u.get('po_id') or '—'} · {u.get('created_at', '')[:16]}"
        )
    return (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего: <b>{total}</b>\n"
        f"✅ Активных: <b>{c['active']}</b>\n"
        f"⏳ В ожидании: <b>{c['pending']}</b>\n"
        f"🚫 Отклонено: <b>{c['banned']}</b>\n\n"
        f"<b>Последние зарегистрированные:</b>\n" + ("\n".join(rows) or "—")
    )