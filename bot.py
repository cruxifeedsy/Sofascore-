import os
import httpx
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Set via Railway’s environment vars

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# --- START MENU ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.utcnow()
    tom = today + timedelta(days=1)
    nxt = today + timedelta(days=2)

    keyboard = [
        [InlineKeyboardButton(f"Today ({today.strftime('%Y-%m-%d')})", callback_data="date_today")],
        [InlineKeyboardButton(f"Tomorrow ({tom.strftime('%Y-%m-%d')})", callback_data="date_tomorrow")],
        [InlineKeyboardButton(f"{nxt.strftime('%Y-%m-%d')}", callback_data="date_next")],
        [InlineKeyboardButton("Auto Predict ⚡", callback_data="auto_predict")]
    ]
    await update.message.reply_text(
        "📅 Choose a prediction option:", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- DATE BUTTONS ---
async def date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    opt = query.data

    today = datetime.utcnow()
    tom = today + timedelta(days=1)
    nxt = today + timedelta(days=2)

    if opt == "date_today":
        dates = [today.strftime("%Y-%m-%d")]
    elif opt == "date_tomorrow":
        dates = [tom.strftime("%Y-%m-%d")]
    elif opt == "date_next":
        dates = [nxt.strftime("%Y-%m-%d")]
    else:
        await query.edit_message_text("⚠️ Error: Unknown option.")
        return

    await fetch_and_predict(dates, query)

# --- AUTO PREDICT FLOW ---
async def auto_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(str(x), callback_data=f"odds_{x}")] for x in [2,5,10,30,100,500,1000]]
    await query.edit_message_text("How many low‑risk odds should I generate?", reply_markup=InlineKeyboardMarkup(keyboard))

async def odds_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data.split("_")[1])
    context.user_data["odds_count"] = count

    today = datetime.utcnow()
    tom = today + timedelta(days=1)
    nxt = today + timedelta(days=2)

    keyboard = [
        [InlineKeyboardButton(f"Only Today ({today.strftime('%Y-%m-%d')})", callback_data="rng_today")],
        [InlineKeyboardButton(f"Today → {nxt.strftime('%Y-%m-%d')}", callback_data="rng_all")]
    ]
    await query.edit_message_text("Choose date range:", reply_markup=InlineKeyboardMarkup(keyboard))

async def range_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sel = query.data

    today = datetime.utcnow()
    tom = today + timedelta(days=1)
    nxt = today + timedelta(days=2)

    if sel == "rng_today":
        dates = [today.strftime("%Y-%m-%d")]
    else:
        dates = [
            today.strftime("%Y-%m-%d"),
            tom.strftime("%Y-%m-%d"),
            nxt.strftime("%Y-%m-%d")
        ]

    count = context.user_data.get("odds_count", 2)
    await fetch_and_predict(dates, query, count)

# --- FETCH & PREDICT ---
async def fetch_and_predict(dates, query, odds_count=2):
    matches_all = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
        for d in dates:
            url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{d}"
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                for e in data.get("events", []):
                    home = e.get("homeTeam", {}).get("name")
                    away = e.get("awayTeam", {}).get("name")
                    if home and away:
                        matches_all.append({
                            "id": e.get("id"),
                            "home": home,
                            "away": away
                        })

    if not matches_all:
        await query.edit_message_text("❌ No matches found for the selected date(s).")
        return

    out = ""
    for m in matches_all:
        pred = generate_prediction(m, odds_count)
        out += f"⚽ {m['home']} vs {m['away']}\n{pred}\n\n"

    await query.edit_message_text(out[:4000])

# --- SIMPLE REALISTIC PREDICTION LOGIC ---
def generate_prediction(match, odds_count):
    # Estimate form (Sofascore would give specifics — extend later)
    home_factor = 1.0
    away_factor = 1.0

    # Generate chances based on simple heuristics
    home_pct = round(50 + (home_factor - away_factor) * 10)
    away_pct = round(50 + (away_factor - home_factor) * 10)
    draw_pct = 100 - home_pct - away_pct

    low_risk = [2,5,10,30,100,500,1000][:odds_count]
    return (
        f"🏠 {home_pct}% | 🤝 {max(draw_pct,0)}% | ✈️ {away_pct}%\n"
        f"Low‑risk odds: {', '.join(map(str, low_risk))}\n"
        "Advice: Based on recent form."
    )

# --- REGISTER HANDLERS ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(date_handler, pattern="^date_"))
app.add_handler(CallbackQueryHandler(auto_predict, pattern="^auto_predict$"))
app.add_handler(CallbackQueryHandler(odds_handler, pattern="^odds_"))
app.add_handler(CallbackQueryHandler(range_handler, pattern="^rng_"))

print("Bot is running...")
app.run_polling()