from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def btn(text, cd):
    return InlineKeyboardButton(text=text, callback_data=cd)


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def welcome_kb(contact):
    rows = [[btn("📩 Отправить ID", "sybid")]]
    if contact:
        rows.append([btn("💬 Написать админу", "contact")])
    rows.append([btn("ℹ️ Как найти ID?", "po_help")])
    return kb(rows)


def cancel_kb():
    return kb([[btn("❌ Отмена", "cancel")]])


def back_kb(cd="adm:menu", label="⬅️ Главное меню"):
    return kb([[btn(label, cd)]])


def approve_kb(tg_id):
    return kb(
        [
            [btn("✅ Одобрить", f"apv:{tg_id}")],
            [btn("❌ Отклонить", f"rej:{tg_id}")],
        ]
    )


def admin_menu_kb():
    return kb(
        [
            [btn("📝 Новые заявки", "adm:pending"), btn("📊 Статистика", "adm:stats")],
            [btn("📡 Сигналы", "adm:signals"), btn("⚙️ Настройки", "adm:settings")],
            [btn("💬 Рассылка", "adm:bcast"), btn("👥 Админы", "adm:admins")],
            [btn("🔄 Обновить", "adm:refresh")],
        ]
    )


def pending_kb(users):
    rows = []
    for u in users:
        uid = str(u["telegram_id"])[-4:]
        rows.append(
            [
                btn(f"✅ {uid}", f"apv:{u['telegram_id']}"),
                btn(f"❌ {uid}", f"rej:{u['telegram_id']}"),
            ]
        )
    rows.append([btn("⬅️ Главное меню", "adm:menu")])
    return kb(rows)


def settings_kb():
    return kb(
        [
            [btn("🔗 Реф. ссылка", "set:referral_link"), btn("🎁 Промокод", "set:promo_code")],
            [btn("👤 Контакт админа", "set:admin_contact"), btn("💰 Мин. депозит ($)", "set:min_deposit")],
            [btn("🔑 AI API Key", "set:openai_key"), btn("🤖 AI Модель", "set:openai_model")],
            [btn("🌐 AI Base URL", "set:openai_base")],
            [btn("⬅️ Главное меню", "adm:menu")],
        ]
    )


def signals_kb():
    return kb(
        [
            [btn("⏯ Вкл / Выкл авто-сигналы", "sig:toggle")],
            [btn("🚀 Сигнал сейчас", "sig:force"), btn("🧪 Тест AI", "sig:test")],
            [btn("📈 Пара", "sig:pairs"), btn("⏱ Интервал", "sig:ints")],
            [btn("🤖 AI-провайдер", "sig:ai")],
            [btn("⬅️ Главное меню", "adm:menu")],
        ]
    )


PAIRS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "PEPEUSDT",
    "TONUSDT",
    "LINKUSDT",
]


def pairs_kb():
    rows = []
    for i in range(0, len(PAIRS), 2):
        pair_a = PAIRS[i]
        row = [btn(pair_a, f"sig:pair:{pair_a}")]
        if i + 1 < len(PAIRS):
            pair_b = PAIRS[i + 1]
            row.append(btn(pair_b, f"sig:pair:{pair_b}"))
        rows.append(row)
    rows.append([btn("✏️ Своя пара", "sig:pair_custom")])
    rows.append([btn("⬅️ Назад", "adm:signals")])
    return kb(rows)


def interval_kb():
    return kb(
        [
            [btn("1 минута", "sig:int:60"), btn("2 минуты", "sig:int:120")],
            [btn("4 минуты", "sig:int:240"), btn("5 минут", "sig:int:300")],
            [btn("⬅️ Назад", "adm:signals")],
        ]
    )


def ai_provider_kb(current):
    mark = {
        "strategy": "⚡ FREE (встроенная стратегия)",
        "openai": "💠 OpenAI-совместимый (Groq/OpenRouter/Gemini...)",
        "neuro": "🧠 NeuroAPI (платно)",
    }
    rows = []
    for key in ("strategy", "openai", "neuro"):
        label = mark[key] + (" ✅" if key == current else "")
        rows.append([btn(label, f"ai:{key}")])
    rows.append([btn("⬅️ Назад", "adm:signals")])
    return kb(rows)


def admins_kb(added_ids, is_owner):
    rows = [[btn("➕ Добавить админа", "adm:add")]]
    if is_owner:
        for aid in added_ids:
            if aid != config_owner():
                rows.append([btn(f"❌ Убрать {aid}", f"admdel:{aid}")])
    rows.append([btn("⬅️ Главное меню", "adm:menu")])
    return kb(rows)


def config_owner():
    import config

    return config.OWNER_ID