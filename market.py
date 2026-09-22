import httpx


class MarketError(Exception):
    pass


async def _get(url, params=None, headers=None, timeout=12):
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


def _ascending(rows):
    return sorted(rows, key=lambda r: r["t"])


async def _binance(pair, limit):
    data = await _get(
        "https://api.binance.com/api/v3/klines",
        {"symbol": pair, "interval": "1m", "limit": limit},
    )
    return [
        {
            "t": int(k[0]),
            "o": float(k[1]),
            "h": float(k[2]),
            "l": float(k[3]),
            "c": float(k[4]),
        }
        for k in data
    ]


async def _bybit(pair, limit):
    data = await _get(
        "https://api.bybit.com/v5/market/kline",
        {"category": "spot", "symbol": pair, "interval": "1", "limit": limit},
    )
    rows = data["result"]["list"]
    return _ascending(
        [
            {
                "t": int(r[0]),
                "o": float(r[1]),
                "h": float(r[2]),
                "l": float(r[3]),
                "c": float(r[4]),
            }
            for r in rows
        ]
    )


async def _okx(pair, limit):
    if pair.endswith("USDT"):
        inst = pair[:-4] + "-USDT"
    elif pair.endswith("USDC"):
        inst = pair[:-4] + "-USDC"
    else:
        inst = pair
    data = await _get(
        "https://www.okx.com/api/v5/market/candles",
        {"instId": inst, "bar": "1m", "limit": limit},
    )
    return _ascending(
        [
            {
                "t": int(r[0]),
                "o": float(r[1]),
                "h": float(r[2]),
                "l": float(r[3]),
                "c": float(r[4]),
            }
            for r in data["data"]
        ]
    )


PROVIDERS = (_binance, _bybit, _okx)


async def get_candles(pair, limit=30):
    errors = []
    for fn in PROVIDERS:
        try:
            rows = await fn(pair, limit)
            if len(rows) >= 5:
                return rows
        except Exception as exc:
            errors.append(f"{fn.__name__.lstrip('_')}: {exc}")
    raise MarketError(" | ".join(errors) or "no data source")