from datetime import datetime, timedelta, timezone


def msk_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=3)))


def welcome(name, ref, promo, contact, min_dep):
    contact_txt = f"@<a href='https://t.me/{contact}'>{contact}</a>" if contact else "нашему администратору"
    return (
        f"👋 Привет, <b>{name}</b>!\n"
        f"Добро пожаловать в сигнальный бот <b>PRO SIGNALS</b> 🚀\n"
        f"Здесь ты будешь получать <b>готовые сигналы в реальном времени</b>.\n\n"
        f"<b>▎Чтобы получить доступ, выполни 5 шагов:</b>\n\n"
        f"1️⃣ Зарегистрируйся на Pocket Option по нашей ссылке:\n"
        f"<a href='{ref}'>▶ Регистрация на Pocket Option</a>\n\n"
        f"2️⃣ При первом депозите введи промокод <b>{promo}</b> и получи <b>+50% к депозиту</b> 🎁\n\n"
        f"3️⃣ Пополни счёт минимум на <b>${min_dep}</b> 💰 — без этого не активируем\n\n"
        f"4️⃣ Пришли свой <b>ID из личного кабинета</b> (кнопка ниже)\n\n"
        f"5️⃣ Дождись подтверждения администратора ⏳\n\n"
        f"⚡️ <b>Хочешь быстрее?</b> Напиши {contact_txt} — активируем в первую очередь!"
    )


PO_HELP = (
    "<b>Как найти свой ID на Pocket Option?</b>\n\n"
    "1. Открой приложение / сайт Pocket Option\n"
    "2. Нажми на свой аватар (Личный кабинет)\n"
    "3. ID указан сверху — это просто число, например <code>38476192</code>\n\n"
    "Пришли это число боту в сообщении 👇"
)

ASK_PO_ID = "📩 Нажми кнопку ниже и пришли свой <b>ID из личного кабинета</b> (обычное число)."

RECEIVED_PO_ID = (
    lambda po_id: (
        f"✅ <b>Принято! Твой Pocket ID:</b> <code>{po_id}</code>\n\n"
        f"Заявка отправлена администратору на проверку.\n"
        f"Как только одобрим — сюда придут сигналы. Обычно это занимает пару минут ⏳"
    )
)


def pending_message(po_id, contact):
    c = f"\nВопросы / ускорить: @{contact}" if contact else ""
    return (
        f"⏳ <b>Заявка на рассмотрении</b>\n\n"
        f"Твоя заявка (Pocket ID: <code>{po_id}</code>) уже у администратора.{c}"
    )


def active_message(pair, interval, ai_label):
    return (
        f"🎉 <b>Ты активирован! Доступ к сигналам открыт.</b>\n\n"
        f"📡 <b>Текущие настройки сигналов:</b>\n"
        f"Пара: <b>{pair}</b>\n"
        f"Таймфрейм: <b>{interval} сек</b>\n"
        f"Модель: <b>{ai_label}</b>\n\n"
        f"Сигналы приходят сюда автоматически. Просто открывай сделку по сигналу 🔥"
    )


def banned_message(contact):
    c = f" Вопросы: @{contact}" if contact else ""
    return f"🚫 <b>Доступ заблокирован.</b>{c}"


def status_text(user, pair, interval, ai_label):
    st = {
        "new": "Новый (требуется активация)",
        "pending": "Заявка на рассмотрении",
        "active": "✅ Активирован",
        "banned": "🚫 Заблокирован",
    }.get(user.get("status"), user.get("status"))
    txt = (
        f"📋 <b>Твой статус:</b> {st}\n"
        f"🆔 Telegram ID: <code>{user['telegram_id']}</code>\n"
        f"💼 Pocket ID: <code>{user.get('po_id') or '—'}</code>\n"
        f"🗓 Регистрация: {user.get('created_at')}\n"
    )
    if user.get("status") == "active":
        txt += (
            f"\n📡 Пара: <b>{pair}</b> · Таймфрейм: <b>{interval}с</b> · Модель: <b>{ai_label}</b>"
        )
    return txt


def admin_hint():
    return "🔑 Ты администратор. Панель управления: /admin"


def signal_text(data):
    direction = (
        f"🟢 <b>CALL (вверх)</b>"
        if data["signal"] == "UP"
        else f"🔴 <b>PUT (вниз)</b>"
    )
    exp = data["exp"].strftime("%H:%M:%S")
    return (
        f"📡 <b>СИГНАЛ | {data['pair']}</b>\n"
        f"⏱ {data['ts']} МСК · Вход в окне ~5 сек | Экспирация {exp}\n\n"
        f"🎯 Направление: {direction}\n"
        f"📊 Уверенность: <b>{data['confidence']}%</b>\n"
        f"🧠 Модель: <b>{data['source']}</b>\n\n"
        f"💡 {data['reason']}\n\n"
        f"⚠️ ММ: 1–2% от депо на сделку. Торговля на бинарных опционах рискованна!"
    )


def broadcast_text(text):
    return "📣 <b>ОБЪЯВЛЕНИЕ</b>\n\n" + text