import os
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = "http://localhost:8000"


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "<b>TurboAZ Price Analyzer</b>\n\n"
        "<b>İki istifadə üsulu var:</b>\n\n"
        "<b>1. Axtarış</b> — nə istədiyinizi yazın:\n"
        "<code>bmw 520 istiyirem ucuz vurugu ola biler</code>\n\n"
        "<b>2. Link analizi</b> — turbo.az linki göndərin:\n"
        "<code>https://turbo.az/autos/10030006-bmw-ix</code>\n\n"
        "Azərbaycanca və ya Rusca yaza bilərsiniz."
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "<b>Necə istifadə etmək olar:</b>\n\n"
        "<b>Axtarış nümunələri:</b>\n"
        "• <code>bmw 520 ucuz</code>\n"
        "• <code>mercedes e class 2015-2018 arasi</code>\n"
        "• <code>toyota 15000 azn-e qeder az gedish</code>\n"
        "• <code>honda civic vurugu ola biler ucuz olsun</code>\n\n"
        "<b>Link analizi:</b>\n"
        "• turbo.az linkini göndərin, AI qiymət analizi verir\n\n"
        "<b>Komandalar:</b>\n"
        "/start — başlanğıc\n"
        "/help — kömək"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "turbo.az" in text:
        await handle_analyze(update, text)
    else:
        await handle_recommend(update, ctx, text)


def build_car_msg(rec, rank_num):
    score = rec.get("score", 0)
    score_label = "Yaxsi" if score >= 70 else "Normal" if score >= 50 else "Zeyif"
    mileage = f"{rec['mileage_km']:,} km" if rec.get("mileage_km") else "N/A"

    return (
        f"<b>{rank_num}. {rec['brand']} {rec['model']} {rec['year']}</b>\n"
        f"Qiymət: <b>{int(rec['price_azn'])} AZN</b>\n"
        f"{rec.get('city', '')} | {mileage} | {rec.get('engine', '')}\n"
        f"Skor: {score}/100 ({score_label})\n"
        f"<i>{rec.get('why', '')}</i>\n"
        f"<a href='{rec['url']}'>Turbo.az-da bax</a>"
    )


async def send_car(update_or_query, rec, rank_num, is_callback=False):
    msg = build_car_msg(rec, rank_num)
    image = rec.get("image")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Elana bax", url=rec["url"])]])

    send_fn = update_or_query.message.reply_photo if not is_callback else update_or_query.message.reply_photo

    if image:
        try:
            await update_or_query.message.reply_photo(
                photo=image,
                caption=msg,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return
        except Exception:
            pass

    await update_or_query.message.reply_text(msg, parse_mode="HTML")


async def handle_recommend(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str):
    wait_msg = await update.message.reply_text("Axtarıram, bir az gözləyin...")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API_URL}/api/recommend", json={"prompt": text})
        data = r.json()
    except Exception as e:
        await wait_msg.delete()
        await update.message.reply_text(f"❌ Xəta: {str(e)}")
        return

    await wait_msg.delete()

    recs = data.get("recommendations", [])
    if not recs:
        await update.message.reply_text("Heç nə tapılmadı. Fərqli söz ilə cəhd edin.")
        return

    parsed = data.get("prompt_parsed", {})
    brand = parsed.get("brand", "") or ""
    model = parsed.get("model", "") or ""
    total = data.get("total_found", 0)

    # Qiymət statistikası
    all_recs = recs
    prices = [r["price_azn"] for r in all_recs if r.get("price_azn")]
    if prices:
        p_min = int(min(prices))
        p_max = int(max(prices))
        p_avg = int(sum(prices) / len(prices))
        stats = (
            f"Min: <b>{p_min:,} AZN</b>  |  "
            f"Orta: <b>{p_avg:,} AZN</b>  |  "
            f"Max: <b>{p_max:,} AZN</b>"
        )
    else:
        stats = ""

    title = f"{brand} {model}".strip() or "Nəticələr"
    header = (
        f"<b>{title}</b> — <b>{total}</b> elan tapıldı\n"
        f"{stats}\n"
        f"─────────────────\n"
        f"<b>Ən yaxşı 5:</b>"
    )
    await update.message.reply_text(header, parse_mode="HTML")

    # İlk 5-i göstər
    for rec in recs[:5]:
        await send_car(update, rec, rec["rank"])

    # ctx.user_data-da bütün nəticələri saxla
    ctx.user_data["all_recs"] = recs
    ctx.user_data["shown"] = 5
    ctx.user_data["prompt"] = text

    # Əgər 5-dən çox nəticə varsa "Daha çox göstər" düyməsi
    if total > 5 and len(recs) > 5:
        remaining = len(recs) - 5
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"Daha çox göstər ({remaining} qalıb)",
                callback_data="show_more"
            )
        ]])
        await update.message.reply_text(
            f"<i>{len(recs)} nəticədən 5-i göstərildi</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )


async def show_more_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    all_recs = ctx.user_data.get("all_recs", [])
    shown = ctx.user_data.get("shown", 5)

    if shown >= len(all_recs):
        await query.edit_message_text("Bütün nəticələr göstərildi.")
        return

    next_batch = all_recs[shown:shown + 5]
    for rec in next_batch:
        msg      = build_car_msg(rec, rec["rank"])
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Elana bax", url=rec["url"])]])
        image    = rec.get("image")
        if image:
            try:
                await query.message.reply_photo(photo=image, caption=msg, parse_mode="HTML", reply_markup=keyboard)
                continue
            except Exception:
                pass
        await query.message.reply_text(msg, parse_mode="HTML")

    new_shown = shown + len(next_batch)
    ctx.user_data["shown"] = new_shown

    remaining = len(all_recs) - new_shown

    if remaining > 0:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"Daha çox göstər ({remaining} qalıb)",
                callback_data="show_more"
            )
        ]])
        await query.edit_message_text(
            f"<i>{len(all_recs)} nəticədən {new_shown}-i göstərildi</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await query.edit_message_text(
            f"<i>Bütün {len(all_recs)} nəticə göstərildi</i>",
            parse_mode="HTML"
        )


async def handle_analyze(update: Update, url: str):
    wait_msg = await update.message.reply_text("Analiz edirəm, bir az gözləyin...")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API_URL}/api/analyze", json={"url": url})
        data = r.json()
    except Exception as e:
        await wait_msg.delete()
        await update.message.reply_text(f"❌ Xəta: {str(e)}")
        return

    await wait_msg.delete()

    listing = data.get("listing", {})
    ai = data.get("ai", {})
    verdict = ai.get("verdict", "")

    pros = ai.get("pros", [])
    cons = ai.get("cons", [])
    pros_text = "\n".join(f"✅ {p}" for p in pros) if pros else "—"
    cons_text = "\n".join(f"❌ {c}" for c in cons) if cons else "—"

    mileage = listing.get("mileage_km", 0) or 0

    msg = (
        f"<b>{listing.get('brand', '')} {listing.get('model', '')} {listing.get('year', '')}</b>\n"
        f"Qiymət: <b>{int(listing.get('price_azn') or 0)} AZN</b>\n"
        f"{listing.get('city', '')} | {mileage:,} km\n\n"
        f"─────────────────\n"
        f"<b>Qiymət: {verdict}</b>\n"
        f"Skor: {ai.get('score', 0)}/100\n"
        f"Bazar qiymətindən fərq: <b>{ai.get('price_diff_percent', 0)}%</b>\n"
        f"Oxşar {data.get('similar_count', 0)} elan ilə müqayisə edildi\n\n"
        f"<b>Xülasə:</b>\n<i>{ai.get('summary', '')}</i>\n\n"
        f"<b>Müsbət:</b>\n{pros_text}\n\n"
        f"<b>Mənfi:</b>\n{cons_text}"
    )

    await update.message.reply_text(msg, parse_mode="HTML")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(show_more_callback, pattern="^show_more$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Bot isleyir...")
    app.run_polling()
