"""Клавиатуры для бота."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ Настройки (ссылки/промо)", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📤 Загрузить видео-гайд", callback_data="admin_upload_video")],
        [InlineKeyboardButton(text="🔄 Сбросить юзера", callback_data="admin_reset_user")],
    ])
    return kb


def admin_settings_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Реф-ссылка", callback_data="edit_ref")],
        [InlineKeyboardButton(text="🎁 Промокод", callback_data="edit_promo")],
        [InlineKeyboardButton(text="📢 Ссылка на канал", callback_data="edit_channel")],
        [InlineKeyboardButton(text="📝 Текст инструкции", callback_data="edit_instruction")],
        [InlineKeyboardButton(text="👀 Посмотреть текущее", callback_data="show_current")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_settings_back")],
    ])
    return kb


def start_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать прогревание", callback_data="start_funnel")],
    ])
    return kb


def funnel_question_keyboard(step_key: str, options: list):
    kb = []
    row = []
    for opt in options:
        row.append(InlineKeyboardButton(text=opt, callback_data=f"funnel_{step_key}_{opt}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)


def final_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="show_instruction")],
        [InlineKeyboardButton(text="🎬 Видео-гайд", callback_data="show_video")],
    ])
    return kb


def video_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Текстовая инструкция", callback_data="show_instruction")],
        [InlineKeyboardButton(text="🔁 Пройти снова", callback_data="start_funnel")],
    ])
    return kb


def instruction_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Видео-гайд", callback_data="show_video")],
        [InlineKeyboardButton(text="🔁 Пройти снова", callback_data="start_funnel")],
    ])
    return kb