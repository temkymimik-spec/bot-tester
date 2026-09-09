"""Модуль хранения данных: локальный JSON-файл (без внешней БД).

Интерфейс методов async (совместим с aiogram), но всё хранится в data/bot_data.json.
Файл пересоздаётся автоматически, папка data/ создаётся при первом запуске.
"""
import json
import os
import time


class Database:
    def __init__(self, path: str = "data/bot_data.json"):
        self.path = path
        self.data = self._load()

    # ---------- синхронное ядро (файл) ----------
    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"settings": self._default_settings(), "users": {}}

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    @staticmethod
    def _default_settings() -> dict:
        return {
            "referral_link": "https://example.com/ref",
            "promo_code": "WELCOME50",
            "video_guide_id": None,
            "private_channel_link": "https://t.me/your_private_channel",
            "instructions": (
                "Инструкция по регистрации:\n"
                "1. Перейдите по реферальной ссылке\n"
                "2. Зарегистрируйтесь\n"
                "3. Примените промокод"
            ),
            "welcome_text": "Привет! Я помогу тебе пройти регистрацию.",
        }

    # ---------- async интерфейс (для вызова из бота) ----------
    async def connect(self):
        # Локальная БД не требует подключения
        pass

    async def close(self):
        self._save()

    async def get_settings(self) -> dict:
        return dict(self.data["settings"])

    async def update_setting(self, key: str, value):
        self.data["settings"][key] = value
        self._save()

    async def get_user(self, user_id: int) -> dict | None:
        return self.data["users"].get(str(user_id))

    async def update_user(self, user_id: int, **kwargs):
        uid = str(user_id)
        user = self.data["users"].get(uid, {"id": user_id})
        user.update(kwargs)
        user["updated_at"] = int(time.time())
        self.data["users"][uid] = user
        self._save()

    async def user_exists(self, user_id: int) -> bool:
        return str(user_id) in self.data["users"]

    async def all_users(self) -> list:
        return list(self.data["users"].values())

    async def users_count(self) -> int:
        return len(self.data["users"])

    async def completed_count(self) -> int:
        return sum(1 for u in self.data["users"].values() if u.get("funnel_done"))