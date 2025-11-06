\
# -*- coding: utf-8 -*-
import os, json, time, asyncio, datetime, math, csv, io
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
import httpx
import feedparser
import yfinance as yf
from pytz import timezone
from urllib.parse import quote_plus
from contextlib import redirect_stdout, redirect_stderr

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

DATA_DIR.mkdir(exist_ok=True, parents=True)

UPDATE_INTERVAL_MIN = int(os.getenv("UPDATE_INTERVAL_MIN", "10"))
TICKERS = [t.strip() for t in os.getenv("TICKERS", "NVDA,SMCI,QQQ").split(",") if t.strip()]
NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "12"))
HISTORY_DAYS = int(os.getenv("HISTORY_DAYS", "30"))
TZ = os.getenv("TZ", "Asia/Taipei")
UA = "Mozilla/5.0 (compatible; MarketMonitorBot/1.0)"
JSON_PATH = DATA_DIR / "dashboard.json"
STOOQ_CACHE: Dict[str, List[Dict[str, Any]]] = {}

# AI Provider Configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").lower()  # openai, anthropic, or none
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)

app = FastAPI(title="Market Monitor")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def now_ts():
    return int(time.time())

def now_iso_tz(tz=TZ):
    tzobj = timezone(tz)
    return datetime.datetime.now(tzobj).strftime("%Y-%m-%d %H:%M:%S %Z")

def _fetch_quote_via_http(ticker: str) -> Optional[Dict[str, Any]]:
    """Use Yahoo quote API directly to reduce yfinance rate-limit errors."""
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={quote_plus(ticker)}"
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    with httpx.Client(timeout=10.0, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    results = data.get("quoteResponse", {}).get("result", [])
    return results[0] if results else None


def _fetch_stooq_series(ticker: str) -> List[Dict[str, Any]]:
    """Fetch daily OHLCV data from Stooq to use as a fallback data source."""
    symbol = f"{ticker.lower()}.us"
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    headers = {
        "User-Agent": UA,
        "Accept": "text/csv",
    }
    with httpx.Client(timeout=10.0, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        text = resp.text.strip()

    if not text:
        return []

    rows: List[Dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        date = row.get("Date")
        close = row.get("Close")
        if not date or not close:
            continue
        try:
            close_val = float(close)
        except (TypeError, ValueError):
            continue

        def to_float(value: Optional[str]) -> Optional[float]:
            if value in (None, "", "0"):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def to_int(value: Optional[str]) -> int:
            if value in (None, "", "0"):
                return 0
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return 0

        rows.append({
            "date": date,
            "close": close_val,
            "open": to_float(row.get("Open")),
            "high": to_float(row.get("High")),
            "low": to_float(row.get("Low")),
            "volume": to_int(row.get("Volume")),
        })

    rows.sort(key=lambda r: r["date"])
    return rows


def get_stooq_series(ticker: str) -> List[Dict[str, Any]]:
    if ticker not in STOOQ_CACHE:
        STOOQ_CACHE[ticker] = _fetch_stooq_series(ticker)
    return STOOQ_CACHE[ticker]


def fetch_price_summary(ticker: str) -> Dict[str, Any]:
    price = None
    currency = "USD"
    exchange = None

    try:
        quote_data = _fetch_quote_via_http(ticker)
        if quote_data:
            price_candidates = [
                quote_data.get("regularMarketPrice"),
                quote_data.get("postMarketPrice"),
                quote_data.get("preMarketPrice"),
                quote_data.get("regularMarketPreviousClose"),
                quote_data.get("previousClose"),
            ]
            for candidate in price_candidates:
                if isinstance(candidate, (int, float)):
                    value = float(candidate)
                    if not math.isnan(value):
                        price = value
                        break
            currency = quote_data.get("currency") or currency
            exchange = quote_data.get("fullExchangeName") or quote_data.get("exchange") or exchange
    except Exception:
        pass

    try:
        stooq_series = get_stooq_series(ticker)
        if stooq_series:
            price = price if price is not None else stooq_series[-1]["close"]
            exchange = exchange or "Stooq"
    except Exception:
        pass

    if price is None:
        try:
            buf_out, buf_err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf_out), redirect_stderr(buf_err):
                tk = yf.Ticker(ticker)
                info = tk.fast_info
                def safe_get(key: str):
                    if not info:
                        return None
                    try:
                        return info.get(key)
                    except Exception:
                        try:
                            return getattr(info, key)
                        except Exception:
                            return None
                for candidate in ("lastPrice", "last_price", "regularMarketPrice", "regularMarketPreviousClose", "previousClose"):
                    val = safe_get(candidate)
                    if val is None:
                        continue
                    try:
                        num = float(val)
                    except (TypeError, ValueError):
                        continue
                    if math.isnan(num):
                        continue
                    price = num
                    break
                if price is None:
                    hist = tk.history(period="5d")
                    if not hist.empty:
                        price = float(hist["Close"].dropna().iloc[-1])
                currency = safe_get('currency') or currency
                exchange = safe_get('exchange') or exchange
        except Exception as e:
            return {"ticker": ticker, "error": f"price_fetch_failed: {e}"}

    return {
        "ticker": ticker,
        "price": price,
        "currency": currency,
        "exchange": exchange,
    }

def fetch_price_history(ticker: str, days: int = 30) -> Dict[str, Any]:
    """獲取歷史價格數據用於圖表"""
    try:
        stooq_series = get_stooq_series(ticker)
        if not stooq_series:
            raise ValueError("stooq_empty")

        recent = stooq_series[-days:]
        dates = [row["date"] for row in recent]
        prices = [row["close"] for row in recent]
        volumes = [row["volume"] for row in recent]

        current = prices[-1] if prices else None
        previous = prices[-2] if len(prices) > 1 else None
        change_pct = 0.0
        if current is not None and previous not in (None, 0):
            change_pct = round(((current - previous) / previous) * 100, 2)
        high_30d = max(prices) if prices else None
        low_30d = min(prices) if prices else None
        valid_volumes = [v for v in volumes if isinstance(v, (int, float))]
        avg_volume = int(sum(valid_volumes) / len(valid_volumes)) if valid_volumes else 0

        return {
            "ticker": ticker,
            "dates": dates,
            "prices": prices,
            "volumes": volumes,
            "stats": {
                "current": current,
                "change_percent": change_pct,
                "high_30d": high_30d,
                "low_30d": low_30d,
                "avg_volume": avg_volume
            }
        }
    except Exception as e:
        return {"ticker": ticker, "error": f"history_fetch_failed: {e}"}

async def fetch_rss(url: str) -> feedparser.FeedParserDict:
    headers = {"User-Agent": UA}
    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return feedparser.parse(r.content)

def google_news_rss_query(query: str, hl="zh-TW", gl="TW", ceid="TW:zh-Hant") -> str:
    q = quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

async def collect_headlines_for(ticker: str) -> List[Dict[str, Any]]:
    queries = {
        "NVDA": ["NVIDIA NVDA", "NVIDIA earnings", "NVIDIA data center AI"],
        "SMCI": ["Super Micro Computer SMCI", "SMCI earnings", "SMCI server AI"],
        "QQQ":  ["Invesco QQQ Nasdaq-100", "QQQ ETF flows", "Nasdaq-100 AI megacap"],
    }
    seen = set()
    items: List[Dict[str, Any]] = []
    for q in queries.get(ticker, [ticker]):
        url = google_news_rss_query(q)
        try:
            feed = await fetch_rss(url)
        except Exception:
            continue
        for e in feed.entries:
            title = e.get("title", "").strip()
            link = e.get("link", "").strip()
            published = e.get("published", "") or e.get("updated", "")
            if not title or not link:
                continue
            key = (title, link)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "title": title,
                "link": link,
                "published": published,
                "source": e.get("source", {}).get("title") if isinstance(e.get("source", {}), dict) else None
            })
    return items[:NEWS_PER_TICKER]

async def generate_ai_analysis(ticker: str, history_data: Dict[str, Any], news_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """使用 AI 生成市場分析（支援 OpenAI GPT 和 Anthropic Claude）"""

    # 準備分析上下文
    stats = history_data.get('stats', {})
    current_price = stats.get('current', 'N/A')
    change_pct = stats.get('change_percent', 0)
    high_30d = stats.get('high_30d', 'N/A')
    low_30d = stats.get('low_30d', 'N/A')
    news_summary = "\n".join([f"- {item['title']}" for item in news_items[:5]])

    prompt = f"""分析 {ticker} 股票的市場狀況：

**當前數據：**
- 當前價格: ${current_price}
- 日變化: {change_pct}%
- 30天高點: ${high_30d}
- 30天低點: ${low_30d}

**最新新聞：**
{news_summary}

請提供簡潔的分析（繁體中文），包括：
1. 整體趨勢判斷（看漲/看跌/中性）
2. 3-5個關鍵要點
3. 簡短總結（50字內）

請以 JSON 格式回應：
{{
  "trend": "bullish/bearish/neutral",
  "summary": "簡短總結",
  "key_points": ["要點1", "要點2", "要點3"]
}}"""

    # OpenAI Provider
    if AI_PROVIDER == "openai" and OPENAI_AVAILABLE and OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "你是專業的股市分析師，提供繁體中文的市場分析。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            response_text = response.choices[0].message.content

            # 嘗試解析 JSON
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                return analysis
            else:
                return {
                    "summary": response_text[:200],
                    "trend": "neutral",
                    "key_points": [response_text[:100]]
                }

        except Exception as e:
            return {"summary": f"OpenAI 分析失敗: {str(e)}", "trend": "neutral", "key_points": []}

    # Anthropic Provider
    elif AI_PROVIDER == "anthropic" and ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.content[0].text

            # 嘗試解析 JSON
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                return analysis
            else:
                return {
                    "summary": response_text[:200],
                    "trend": "neutral",
                    "key_points": [response_text[:100]]
                }

        except Exception as e:
            return {"summary": f"Anthropic 分析失敗: {str(e)}", "trend": "neutral", "key_points": []}

    # No AI Provider
    else:
        provider_status = AI_PROVIDER if AI_PROVIDER != "none" else "未設定"
        return {
            "summary": f"AI 分析未啟用（Provider: {provider_status}）",
            "trend": "neutral",
            "key_points": []
        }

async def build_json():
    STOOQ_CACHE.clear()
    data = {
        "generated_at_unix": now_ts(),
        "generated_at_local": now_iso_tz(),
        "tickers": {},
        "meta": {"interval_min": UPDATE_INTERVAL_MIN, "tz": TZ, "history_days": HISTORY_DAYS}
    }

    for t in TICKERS:
        price_summary = fetch_price_summary(t)
        price_history = fetch_price_history(t, HISTORY_DAYS)
        news_items = await collect_headlines_for(t)

        # 生成 AI 分析
        ai_analysis = await generate_ai_analysis(t, price_history, news_items)

        data["tickers"][t] = {
            "price": price_summary,
            "history": price_history,
            "news": news_items,
            "ai_analysis": ai_analysis
        }

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data

async def refresher_loop():
    if not JSON_PATH.exists():
        await build_json()
    while True:
        try:
            await build_json()
        except Exception as e:
            err = {"generated_at_unix": now_ts(),"generated_at_local": now_iso_tz(),"error": str(e)}
            JSON_PATH.write_text(json.dumps(err, ensure_ascii=False, indent=2), encoding="utf-8")
        await asyncio.sleep(UPDATE_INTERVAL_MIN * 60)

@app.on_event("startup")
async def on_start():
    asyncio.create_task(refresher_loop())

@app.get("/", response_class=HTMLResponse)
def index():
    tpl = env.get_template("dashboard.html")
    return tpl.render()

@app.get("/data/dashboard.json")
def data_json():
    if JSON_PATH.exists():
        return JSONResponse(content=json.loads(JSON_PATH.read_text(encoding="utf-8")))
    return JSONResponse(content={"status":"initializing"}, status_code=202)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8088, workers=1)
