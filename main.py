import os
import json
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler, ContextTypes
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- States ---
STEP_NAME, STEP_SELECT_NUMBER, STEP_QUESTIONS = range(3)

# --- Google Sheets setup ---
def init_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
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

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("شروع", callback_data="start")]]
    await update.message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image1.jpg",
        caption="به ربات خوش آمدید!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# --- Start button pressed ---
async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("نام و نام خانوادگی خود را وارد کنید:")
    return STEP_NAME

# --- Receive Name ---
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    # Show number selection
    keyboard = [[InlineKeyboardButton(str(i), callback_data=f"num_{i}")] for i in range(1, 10)]
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
    await send_question(query.message, context)
    return STEP_QUESTIONS

# --- Send question with navigation ---
async def send_question(message, context):
    q_index = context.user_data["current_q"]
    question_text = QUESTIONS[q_index]
    answer = context.user_data["answers"][q_index]

    buttons = []
    if q_index > 0:
        buttons.append(InlineKeyboardButton("⬅ سوال قبل", callback_data="prev"))
    if q_index < len(QUESTIONS) - 1:
        buttons.append(InlineKeyboardButton("➡ سوال بعد", callback_data="next"))
    buttons.append(InlineKeyboardButton("✅ ثبت پاسخ", callback_data="submit"))

    await message.reply_text(
        f"{question_text}

پاسخ فعلی: {answer or '---'}",
        reply_markup=InlineKeyboardMarkup([buttons])
    )

# --- Handle text answer ---
async def receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_index = context.user_data["current_q"]
    context.user_data["answers"][q_index] = update.message.text
    # سوال فعلی رو دوباره نشون میدیم با جواب جدید
    await send_question(update.message, context)
    return STEP_QUESTIONS

# --- Navigation buttons ---
async def nav_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    q_index = context.user_data["current_q"]

    if query.data == "prev":
        context.user_data["current_q"] -= 1
    elif query.data == "next":
        context.user_data["current_q"] += 1
    elif query.data == "submit":
        await submit_all(query.message, context)
        return ConversationHandler.END

    await send_question(query.message, context)
    return STEP_QUESTIONS

# --- Submit all ---
async def submit_all(message, context: ContextTypes.DEFAULT_TYPE):
    data_row = [
        context.user_data.get("name", ""),
        context.user_data.get("selected_number", "")
    ]
    data_row.extend(context.user_data.get("answers", []))
    SHEET.append_row(data_row)
    await message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image3.jpg",
        caption="اطلاعات شما با موفقیت ثبت شد. ممنون!"
    )

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
                CallbackQueryHandler(nav_buttons, pattern="^(prev|next|submit)$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
