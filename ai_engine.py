import json
import re
from datetime import datetime

import httpx

SYSTEM_FINANCE = (
    "You are a professional intraday market analyst for ONE-MINUTE binary options."
    "You analyze 1-minute candles and predict ONLY the direction of the price 1 minute ahead."
    "You output strict JSON and nothing else. You never make guarantees."
)

PROMPT_TEMPLATE = """Пара: {pair}. Таймфрейм: 1 минута (для бинарных опционов, экспирация ~1 мин).

Последние {n} свечей (время МСК, open, high, low, close):
{candles}

Задача: спрогнозируй движение цены {pair} через 1 минуту.
Учитывай: тренд (EMA 7/21), RSI, импульс, свечные паттерны, волатильность.

Верни СТРОГО один JSON объект без markdown и без пояснений:
{{"signal": "UP", "confidence": 70, "reason": "краткое обоснование на русском, 1-2 предложения"}}

UP = цена будет выше, DOWN = цена будет ниже. confidence — целое число от 51 до 99."""


def _build_prompt(pair, candles):
    lines = []
    for c in candles[-24:]:
        ts = datetime.fromtimestamp(c["t"] / 1000).strftime("%H:%M:%S")
        lines.append(f"{ts} O={c['o']:.5f} H={c['h']:.5f} L={c['l']:.5f} C={c['c']:.5f}")
    return PROMPT_TEMPLATE.format(pair=pair, n=len(candles[-24:]), candles="\n".join(lines))


def _extract_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text).strip(), flags=re.M).strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no json found in answer")
    return json.loads(match.group(0))


def _parse(data):
    sig_raw = str(data.get("signal") or data.get("direction") or "").upper()
    if sig_raw in ("UP", "CALL", "BUY"):
        signal = "UP"
    elif sig_raw in ("DOWN", "PUT", "SELL"):
        signal = "DOWN"
    else:
        raise ValueError(f"bad signal: {sig_raw!r}")
    try:
        confidence = int(data.get("confidence", data.get("accuracy", 60)))
    except (TypeError, ValueError):
        confidence = 60
    confidence = max(51, min(99, confidence))
    reason = str(data.get("reason") or data.get("comment") or "").strip()
    return {"signal": signal, "confidence": confidence, "reason": reason, "source": "AI"}


async def _post_json(url, headers, payload, timeout=50):
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def ask_openai_compat(pair, candles, base, key, model):
    url = base.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_FINANCE},
            {"role": "user", "content": _build_prompt(pair, candles)},
        ],
        "temperature": 0.2,
    }
    data = await _post_json(url, headers, payload)
    content = data["choices"][0]["message"]["content"]
    return _parse(_extract_json(content))


async def ask_neuro(pair, candles, key, mode="smart"):
    url = "https://api.neurobro.ai/api/v1/agent/ask"
    headers = {"X-API-Key": key, "Content-Type": "application/json"}
    payload = {
        "prompt": _build_prompt(pair, candles),
        "mode": mode,
        "stream": False,
        "system_prompt": SYSTEM_FINANCE,
        "message_history": [],
    }
    data = await _post_json(url, headers, payload)
    answer = data.get("answer") or data.get("output")
    if isinstance(answer, dict):
        return _parse(answer)
    return _parse(_extract_json(str(answer)))


def ema(vals, n):
    k = 2 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, n=14):
    if len(closes) <= n:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains[:n]) / n
    avg_l = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        avg_g = (avg_g * (n - 1) + gains[i]) / n
        avg_l = (avg_l * (n - 1) + losses[i]) / n
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


def strategy(candles):
    closes = [c["c"] for c in candles]
    fast = ema(closes, 7)
    slow = ema(closes, 21)
    r = rsi(closes)
    f1, f0 = fast[-1], fast[-2]
    s1, s0 = slow[-1], slow[-2]
    last, prev = closes[-1], closes[-2]

    if f0 <= s0 and f1 > s1:
        sig, conf = "UP", 74
        reason = "Бычье пересечение EMA(7) над EMA(21) — импульс вверх"
    elif f0 >= s0 and f1 < s1:
        sig, conf = "DOWN", 74
        reason = "Медвежье пересечение EMA(7) под EMA(21) — импульс вниз"
    elif r <= 30:
        sig, conf = "UP", min(80, 50 + int((30 - r)))
        reason = f"Перепроданность (RSI {r:.0f}) — ожидаем отскок вверх"
    elif r >= 70:
        sig, conf = "DOWN", min(80, 50 + int((r - 70)))
        reason = f"Перекупленность (RSI {r:.0f}) — ожидаем откат вниз"
    else:
        sig = "UP" if last >= prev else "DOWN"
        conf = 55
        reason = "Короткий импульс последней свечи и нейтральные индикаторы"
    return {"signal": sig, "confidence": conf, "reason": reason, "source": "Strategy"}


async def generate_signal(db, pair, candles):
    provider = await db.get_setting("ai_provider", "strategy")
    if provider == "neuro":
        key = await db.get_setting("neuro_key", "")
        if key:
            try:
                return await ask_neuro(pair, candles, key)
            except Exception:
                pass
    elif provider == "openai":
        base = await db.get_setting("openai_base", "")
        key = await db.get_setting("openai_key", "")
        model = await db.get_setting("openai_model", "")
        if base:
            try:
                return await ask_openai_compat(pair, candles, base, key, model)
            except Exception:
                pass
    return strategy(candles)


async def test_ai(db, pair):
    from market import exchange_symbol, get_candles

    candles = await get_candles(exchange_symbol(pair))
    provider = await db.get_setting("ai_provider", "strategy")

    if provider == "neuro":
        key = await db.get_setting("neuro_key", "")
        if not key:
            return False, "🧠 Выбран NeuroAPI, но ключ пуст. Вставь ключ в ⚙️ Настройки."
        try:
            res = await ask_neuro(pair, candles, key)
        except Exception as exc:
            return False, f"🧠 NeuroAPI ошибка: {exc}"
        return True, _result_text(res, "NeuroAPI")

    if provider == "openai":
        base = await db.get_setting("openai_base", "")
        key = await db.get_setting("openai_key", "")
        model = await db.get_setting("openai_model", "")
        if not base:
            return False, "💠 Не задан AI Base URL. Добавь в ⚙️ Настройках."
        try:
            res = await ask_openai_compat(pair, candles, base, key, model)
        except Exception as exc:
            return False, f"💠 Ошибка AI API ({base}): {exc}"
        return True, _result_text(res, model)

    res = strategy(candles)
    return True, _result_text(res, "Strategy")


def _result_text(res, model):
    return (
        f"Направление: <b>{res['signal']}</b>, уверенность <b>{res['confidence']}%</b>\n"
        f"💡 {res['reason']}"
    )


async def provider_label(db):
    provider = await db.get_setting("ai_provider", "strategy")
    if provider == "neuro":
        return "NeuroAPI 🧠"
    if provider == "openai":
        model = await db.get_setting("openai_model", "")
        return model or "OpenAI-compat 💠"
    return "Стратегия (FREE) ⚡"