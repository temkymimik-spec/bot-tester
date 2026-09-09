"""Логика воронки прогрева пользователя."""
import logging
from keyboards import funnel_question_keyboard, final_keyboard

logger = logging.getLogger(__name__)

# Шаги воронки. Ключ = ключ шага, value = {"question", "options", "store_key"}
FUNNEL_STEPS = [
    {
        "key": "age",
        "question": "Сколько вам лет?",
        "options": ["18-25", "26-35", "36-45", "45+"],
        "store_key": "age",
    },
    {
        "key": "exp",
        "question": "Как давно вы в трейдинге?",
        "options": ["Только начинаю", "До года", "1-3 года", "Более 3 лет"],
        "store_key": "exp",
    },
    {
        "key": "capital",
        "question": "Какой у вас стартовый капитал?",
        "options": ["До $500", "$500-$2K", "$2K-$10K", "Более $10K"],
        "store_key": "capital",
    },
    {
        "key": "goal",
        "question": "Какая ваша главная цель?",
        "options": ["Стабильный доход", "Быстрый разгон", "Научиться стратегиям", "Пассивный доход"],
        "store_key": "goal",
    },
]

# Конечный этап после прохождения воронки
STEP_INDEX = {s["key"]: i for i, s in enumerate(FUNNEL_STEPS)}


def first_step_key() -> str:
    return FUNNEL_STEPS[0]["key"]


def get_step_by_key(key: str):
    for s in FUNNEL_STEPS:
        if s["key"] == key:
            return s
    return None


def build_final_message(s: dict, user) -> str:
    """Формирует финальное сообщение с инструкцией, ссылками и промокодом."""
    lines = [
        "🎉 <b>Поздравляю! Вы прошли квалификацию.</b>\n",
        "Вот ваш полный гайд для регистрации:",
        "",
        "━━━━━━━━━━━━━━━",
        f"📝 <b>Инструкция:</b>",
        s.get("instructions", ""),
        "",
        f"🔗 <b>Реферальная ссылка:</b>",
        f"{s.get('referral_link', '')}",
        "",
        f"🎁 <b>Промокод:</b> <code>{s.get('promo_code', '')}</code>",
        "",
        f"📢 <b>Приватный канал:</b>",
        f"{s.get('private_channel_link', '')}",
        "",
        "Смотри видео-гайд 👇",
    ]
    return "\n".join(lines)


async def process_funnel_answer(call, db):
    """Обрабатывает ответ на вопрос воронки и двигает к следующему шагу."""
    data = call.data  # формат: funnel_<key>_<value>
    parts = data.split("_")
    step_key = parts[1]
    value = "_".join(parts[2:])  # значение может содержать пробелы и символы

    # Восстановим исходный текст опции
    step = get_step_by_key(step_key)
    answer_text = None
    if step:
        for opt in step["options"]:
            if opt.replace(" ", "_") == value or opt.replace(" ", "_") == value.replace(" ", "_"):
                answer_text = opt
                break

    user_id = call.from_user.id
    store_key = step["store_key"] if step else step_key
    await db.update_user(user_id, **{store_key: answer_text or value})
    await db.update_user(user_id, step=step_key)

    idx = STEP_INDEX.get(step_key, 0)
    if idx + 1 >= len(FUNNEL_STEPS):
        # Воронка завершена -> финальный экран
        await db.update_user(user_id, funnel_done=True, step="completed")
        settings = await db.get_settings()
        msg = build_final_message(settings, await db.get_user(user_id))
        try:
            await call.message.edit_text(msg, reply_markup=final_keyboard(), parse_mode="HTML")
        except Exception as e:
            logger.warning("Ошибка edit final msg: %s", e)
            await call.message.answer(msg, reply_markup=final_keyboard(), parse_mode="HTML")
        return

    # Следующий вопрос
    next_step = FUNNEL_STEPS[idx + 1]
    kb = funnel_question_keyboard(next_step["key"], next_step["options"])
    try:
        await call.message.edit_text(
            f"<b>{next_step['question']}</b>",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Ошибка edit next q: %s", e)
        await call.message.answer(f"<b>{next_step['question']}</b>", reply_markup=kb, parse_mode="HTML")
