import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler, ContextTypes
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Logging ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- States ---
STEP_NAME, STEP_SELECT_NUMBER, STEP_QUESTIONS = range(3)

# --- Google Sheets setup ---
def init_gsheet():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    service_account_info = json.loads(os.environ["GOOGLE_SA_KEY"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ["SPREADSHEET_ID"]).sheet1
    return sheet

SHEET = init_gsheet()

# --- Questions ---
QUESTIONS = [
    "سوال اول: ...",
    "سوال دوم: ...",
    "سوال سوم: ...",
    "سوال چهارم: ..."
]

# --- Start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("شروع", callback_data="start")]]
    await update.message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image1.jpg",
        caption="به ربات خوش آمدید!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# --- Start button ---
async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("نام و نام خانوادگی خود را وارد کنید:")
    return STEP_NAME

# --- Receive Name ---
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text

    # Create 3-column button layout (1-9)
    keyboard = []
    for i in range(1, 10, 3):
        row = [
            InlineKeyboardButton(str(i), callback_data=f"num_{i}"),
            InlineKeyboardButton(str(i+1), callback_data=f"num_{i+1}"),
            InlineKeyboardButton(str(i+2), callback_data=f"num_{i+2}")
        ]
        keyboard.append(row)

    await update.message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image2.jpg",
        caption="یک عدد از ۱ تا ۹ انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STEP_SELECT_NUMBER

# --- Number selected ---
async def select_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    number = query.data.split("_")[1]
    context.user_data["selected_number"] = number
    context.user_data["answers"] = [""] * len(QUESTIONS)
    context.user_data["current_q"] = 0

    # Ask first question
    await query.message.reply_text(QUESTIONS[0])
    return STEP_QUESTIONS

# --- Receive answer for questions sequentially ---
async def receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_index = context.user_data["current_q"]
    context.user_data["answers"][q_index] = update.message.text

    if q_index < len(QUESTIONS) - 1:
        context.user_data["current_q"] += 1
        await update.message.reply_text(QUESTIONS[context.user_data["current_q"]])
        return STEP_QUESTIONS
    else:
        # Last question answered → show Submit button
        keyboard = [[InlineKeyboardButton("✅ ثبت نهایی", callback_data="submit")]]
        await update.message.reply_text(
            text="برای ارسال پاسخ‌ها روی دکمه زیر بزنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return STEP_QUESTIONS

# --- Submit all answers ---
async def submit_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data_row = [
        context.user_data.get("name", ""),
        context.user_data.get("selected_number", "")
    ]
    data_row.extend(context.user_data.get("answers", []))
    SHEET.append_row(data_row)

    await query.message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image3.jpg",
        caption="اطلاعات شما با موفقیت ثبت شد. ممنون!"
    )
    return ConversationHandler.END

# --- Cancel ---
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
            STEP_SELECT_NUMBER: [CallbackQueryHandler(select_number, pattern="^num_")],
            STEP_QUESTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_answer),
                CallbackQueryHandler(submit_all, pattern="^submit$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
