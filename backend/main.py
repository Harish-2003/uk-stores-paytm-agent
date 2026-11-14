"""UK Stores Srikakulam - FastAPI backend.
Groq (gpt-oss) is the brain. Paytm MCP is attached by default as a remote MCP tool
(Groq's servers call it). Store actions (sales, discounts, coins) are local tools."""
import os, json, random, datetime as dt
from pathlib import Path
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
BASE = "https://api.groq.com/openai/v1"
MCP_URL = os.getenv("PAYTM_MCP_URL", "https://paytm-mcp.pg2prod.paytm.com/sse/")
MCP_ID = os.getenv("PAYTM_MCP_CLIENT_ID", "")
MCP_TOKEN = os.getenv("PAYTM_MCP_TOKEN", "")
MCP_ON = bool(MCP_ID and MCP_TOKEN)

app = FastAPI(title="UK Stores API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- demo store data (replace with real data later) ----------
random.seed(7)
ITEMS = [("Rice 5kg", 320), ("Toor Dal 1kg", 160), ("Sunflower Oil 1L", 145), ("Sugar 1kg", 48),
         ("Tea 250g", 120), ("Biscuits", 30), ("Soap", 42), ("Milk 500ml", 28)]
CUSTOMERS = ["Ramesh", "Lakshmi", "Venkat", "Sita", "Appala Naidu", "Padma", "Gopi", "Saraswati"]
MODES = ["UPI", "Soundbox QR", "Soundbox QR", "Card", "Cash"]
today = dt.date.today()
DAILY = [{"date": (today - dt.timedelta(days=6 - i)).strftime("%a"), "sales": random.randint(9000, 18000)} for i in range(7)]
ORDERS = []
for i in range(12):
    it = random.choice(ITEMS); q = random.randint(1, 4)
    ORDERS.append({"id": f"UK{1040 + i}", "customer": random.choice(CUSTOMERS), "item": it[0],
                   "amount": it[1] * q, "mode": random.choice(MODES), "time": f"{9 + i}:{random.randint(10, 59)}"})
ORDERS.reverse()
TOP = [{"item": n, "units": random.randint(20, 90)} for n, _ in ITEMS[:6]]
TOP.sort(key=lambda x: -x["units"])
SEGMENTS = {"regular": 142, "new": 38, "lapsed": 21}
DB = {"discounts": [], "coins": [], "voice": []}
MOCK_SETTLEMENT = {"date": str(today), "orders": 64, "gross": 14820, "refunds": 520, "fees": 118, "payout": 14182,
                   "expected_from_bills": 14822, "note": "Demo data - Paytm MCP not connected"}

# ---------- local store tools ----------
def sales_summary(days: int = 7):
    d = DAILY[-max(1, min(days, 7)):]
    return {"days": d, "total": sum(x["sales"] for x in d), "top_items": TOP[:3]}

def create_discount(segment: str, percent: int, valid_days: int = 7):
    r = {"segment": segment, "percent": percent, "valid_days": valid_days,
         "customers": SEGMENTS.get(segment, 0), "code": f"UK{percent}{segment[:3].upper()}"}
    DB["discounts"].append(r); return r

def grant_coins(segment: str, coins: int, reason: str = "Thank you from UK Stores"):
    r = {"segment": segment, "coins_each": coins, "customers": SEGMENTS.get(segment, 0), "reason": reason}
    DB["coins"].append(r); return r

def soundbox_announce(text: str):
    DB["voice"].append({"text": text, "at": dt.datetime.now().strftime("%H:%M")}); return {"queued": text}

IMPL = {"sales_summary": sales_summary, "create_discount": create_discount,
        "grant_coins": grant_coins, "soundbox_announce": soundbox_announce}
S = lambda n, d, p, req=(): {"type": "function", "function": {"name": n, "description": d,
    "parameters": {"type": "object", "properties": p, "required": list(req)}}}
TOOLS = [
    S("sales_summary", "Sales for last N days and top items", {"days": {"type": "integer"}}),
    S("create_discount", "Create a percentage discount for a customer segment (regular/new/lapsed)",
      {"segment": {"type": "string"}, "percent": {"type": "integer"}, "valid_days": {"type": "integer"}}, ("segment", "percent")),
    S("grant_coins", "Give Paytm Coins (DineCash-style rewards) to a segment",
      {"segment": {"type": "string"}, "coins": {"type": "integer"}, "reason": {"type": "string"}}, ("segment", "coins")),
    S("soundbox_announce", "Queue a short voice announcement for the Soundbox", {"text": {"type": "string"}}, ("text",)),
]
SYSTEM = ("You are Lakshmi, the voice store manager for UK Stores, Srikakulam. Replies are spoken aloud: "
          "max 3 short sentences, amounts in rupees, no markdown. Use tools for any store action, then say what you did. "
          "Never run a refund or any money movement unless the user message starts with [CONFIRMED].")

# ---------- Groq ----------
async def groq(path, body):
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(f"{BASE}/{path}", json=body, headers={"Authorization": f"Bearer {GROQ_KEY}"})
        r.raise_for_status(); return r.json()

async def store_agent(message, extra_system=""):
    msgs = [{"role": "system", "content": SYSTEM + extra_system}, {"role": "user", "content": message}]
    actions = []
    for _ in range(5):
        m = (await groq("chat/completions", {"model": MODEL, "messages": msgs, "tools": TOOLS,
                                              "tool_choice": "auto"}))["choices"][0]["message"]
        if not m.get("tool_calls"):
            return m.get("content") or "Done.", actions
        msgs.append({"role": "assistant", "content": m.get("content"), "tool_calls": m["tool_calls"]})
        for tc in m["tool_calls"]:
            name = tc["function"]["name"]
            try: args = json.loads(tc["function"]["arguments"] or "{}"); out = IMPL[name](**args)
            except Exception as e: args, out = {}, {"error": str(e)}
            actions.append({"tool": name, "args": args, "result": out})
            msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(out)})
    return "I ran out of steps. Please try again.", actions

async def mcp_agent(message):
    body = {"model": MODEL, "instructions": SYSTEM, "input": message,
            "tools": [{"type": "mcp", "server_label": "paytm", "server_url": MCP_URL,
                       "headers": {"client-id": MCP_ID, "Authorization": f"Bearer {MCP_TOKEN}"}}]}
    res = await groq("responses", body)
    text = res.get("output_text") or ""
    calls = []
    for o in res.get("output", []):
        if o.get("type") == "message":
            text = text or "".join(c.get("text", "") for c in o.get("content", []))
        if "mcp_call" in o.get("type", ""):
            calls.append({"tool": o.get("name", "paytm_mcp"), "args": o.get("arguments"), "result": "via Paytm MCP"})
    return text or "No reply from Paytm MCP.", calls

# ---------- routes ----------
class Ask(BaseModel):
    message: str
    scope: str = "store"      # "mcp" = Paytm payments, "store" = discounts/coins/sales
    confirmed: bool = False

@app.get("/api/status")
def status():
    return {"groq": bool(GROQ_KEY), "mcp": MCP_ON, "model": MODEL}

@app.get("/api/dashboard")
def dashboard():
    total = sum(d["sales"] for d in DAILY)
    return {"kpis": {"week_sales": total, "today": DAILY[-1]["sales"], "orders": len(ORDERS) * 5,
                     "avg_bill": round(total / (len(ORDERS) * 35))},
            "daily": DAILY, "top": TOP, "orders": ORDERS, "segments": SEGMENTS,
            "discounts": DB["discounts"], "coins": DB["coins"], "voice": DB["voice"][-5:],
            "settlement": MOCK_SETTLEMENT}

@app.post("/api/agent")
async def agent(a: Ask):
    if not GROQ_KEY:
        return {"reply": "Add GROQ_API_KEY to backend/.env and restart the server.", "actions": [], "mode": "error"}
    if a.scope == "mcp" and "refund" in a.message.lower() and not a.confirmed:
        return {"needs_confirmation": True}
    msg = ("[CONFIRMED] " if a.confirmed else "") + a.message
    try:
        if a.scope == "mcp" and MCP_ON:
            reply, actions = await mcp_agent(msg); mode = "paytm-mcp"
        elif a.scope == "mcp":
            reply, actions = await store_agent(msg, " DEMO MODE: Paytm MCP is not connected. Answer only from this mock data and say it is demo data: "
                                               + json.dumps(MOCK_SETTLEMENT) + " Orders: " + json.dumps(ORDERS[:5]))
            mode = "demo"
        else:
            reply, actions = await store_agent(msg); mode = "store"
        return {"reply": reply, "actions": actions, "mode": mode}
    except httpx.HTTPStatusError as e:
        return {"reply": f"Groq error {e.response.status_code}: {e.response.text[:200]}", "actions": [], "mode": "error"}
    except Exception as e:
        return {"reply": f"Something failed: {e}", "actions": [], "mode": "error"}

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
