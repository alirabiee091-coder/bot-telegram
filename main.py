import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler, ContextTypes
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- States ---
STEP_NAME, STEP_SELECT_TYPE, STEP_DYNAMIC_QUESTIONS = range(3)

# --- Google Sheets setup ---
def init_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    service_account_info = json.loads(os.environ["GOOGLE_SA_KEY"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ["SPREADSHEET_ID"]).sheet1
    return sheet

SHEET = init_gsheet()

# --- Questions by type ---
QUESTIONS_BY_TYPE = {
    "hero": [
        {"q": "قدرت یا توانایی اصلی او چیست؟", "options": ["💪 قدرت فیزیکی", "⚡ سرعت", "⏳ کنترل زمان"]},
        {"q": "ویژگی شخصیتی محوری او چیست؟", "options": ["🦸 شجاعت", "❤️ ازخودگذشتگی", "⚖️ عدالت‌خواهی"]}
    ],
    "monster": [
        {"q": "حالت کلی احساس هیولا چیست؟", "options": ["😊 بامزه", "👹 ترسناک", "🌀 مرموز"]},
        {"q": "رنگ غالب هیولا چیست؟", "options": ["⚫🟣 مشکی و بنفش", "🟢⚫ سبز و سیاه", "🔴🟡 قرمز و زرد"]}
    ]
    # بقیه دسته‌ها رو مثل قبل می‌تونی کامل کنی
}

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("شروع", callback_data="start")]]
    await update.message.reply_text(
        "به ربات خوش آمدید!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("نام و نام خانوادگی خود را وارد کنید:")
    return STEP_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    keyboard = [
        [InlineKeyboardButton("🦸‍♂️ قهرمان درون", callback_data="type_hero"),
         InlineKeyboardButton("🐉 هیولای درون", callback_data="type_monster")]
    ]
    await update.message.reply_text(
        "یک گزینه را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STEP_SELECT_TYPE

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    type_key = query.data.split("_", 1)[1]
    context.user_data["selected_type"] = type_key
    context.user_data["current_q"] = 0
    context.user_data["answers"] = []
    await send_question(query.message, context)
    return STEP_DYNAMIC_QUESTIONS

async def send_question(message, context):
    type_key = context.user_data["selected_type"]
    q_index = context.user_data["current_q"]
    total_q = len(QUESTIONS_BY_TYPE[type_key])
    q_data = QUESTIONS_BY_TYPE[type_key][q_index]
    keyboard = []
    row = []
    for option in q_data["options"]:
        row.append(InlineKeyboardButton(option, callback_data=f"ans_{option}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    await message.reply_text(
        f"سوال {q_index+1} از {total_q}:\n{q_data['q']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def answer_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    answer_text = query.data.split("_", 1)[1]
    context.user_data["answers"].append(answer_text)

    # ✅ پیام تایید انتخاب
    await query.message.reply_text(f"✅ انتخاب شما: {answer_text}")
    await asyncio.sleep(0.7)

    if context.user_data["current_q"] < len(QUESTIONS_BY_TYPE[context.user_data["selected_type"]]) - 1:
        context.user_data["current_q"] += 1
        await send_question(query.message, context)
        return STEP_DYNAMIC_QUESTIONS
    else:
        SHEET.append_row([
            context.user_data.get("name", ""),
            context.user_data.get("selected_type", "")
        ] + context.user_data["answers"])
        await query.message.reply_text("اطلاعات شما با موفقیت ثبت شد. ممنون! 🎉")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("فرآیند لغو شد.")
    return ConversationHandler.END

# --- Main ---
def main():
    app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_button, pattern="^start$")
        ],
        states={
            STEP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            STEP_SELECT_TYPE: [CallbackQueryHandler(select_type, pattern="^type_")],
            STEP_DYNAMIC_QUESTIONS: [CallbackQueryHandler(answer_selected, pattern="^ans_")]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
