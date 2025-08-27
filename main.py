import os
import json
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------- Logger ----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

# ---------------- States ----------------
STEP_NAME, STEP_SELECT_NUMBER, STEP_QUESTIONS = range(3)

# ---------------- Google Sheets Setup ----------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
service_account_info = json.loads(os.environ["GOOGLE_SA_KEY"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ["SPREADSHEET_ID"]).sheet1

# ---------------- Questions ----------------
QUESTIONS = [
    "سوال اول را پاسخ دهید:",
    "سوال دوم را پاسخ دهید:",
    "سوال سوم را پاسخ دهید:",
    "سوال چهارم را پاسخ دهید:"
]

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش تصویر شروع و دکمه شروع"""
    keyboard = [[InlineKeyboardButton("شروع", callback_data="start")]]
    await update.message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image1.jpg",
        caption="به ربات خوش آمدید!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END  # مکالمه از طریق دکمه شروع آغاز می‌شود

async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع گرفتن نام بعد از زدن دکمه شروع"""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("لطفاً نام و نام خانوادگی خود را وارد کنید:")
    return STEP_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ذخیره نام و رفتن به انتخاب عدد"""
    context.user_data["name"] = update.message.text.strip()

    # تصویر دکمه‌های عددی
    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(1, 6)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(6, 10)]
    ]
    await update.message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image2.jpg",
        caption="یک عدد را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STEP_SELECT_NUMBER

async def select_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ذخیره عدد انتخابی و رفتن به سوال اول"""
    query = update.callback_query
    await query.answer()
    number = query.data.split("_")[1]
    context.user_data["selected_number"] = number
    context.user_data["answers"] = [""] * len(QUESTIONS)
    context.user_data["current_q"] = 0

    # نمایش سوال اول
    keyboard = [[InlineKeyboardButton("سوال بعد ➡", callback_data="next_q")]]
    await query.message.reply_text(QUESTIONS[0], reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_QUESTIONS

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ذخیره پاسخ فعلی و انتظار دستور بعدی"""
    current_q = context.user_data["current_q"]
    context.user_data["answers"][current_q] = update.message.text.strip()
    return STEP_QUESTIONS

async def navigate_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جابجایی بین سوالات"""
    query = update.callback_query
    await query.answer()
    current_q = context.user_data["current_q"]

    # ذخیره متن آخرین پیام
    if query.message.reply_to_message and query.message.reply_to_message.text:
        context.user_data["answers"][current_q] = query.message.reply_to_message.text.strip()

    if query.data == "next_q":
        if current_q < len(QUESTIONS) - 1:
            context.user_data["current_q"] += 1
        else:
            # سوال آخر -> دکمه ثبت نهایی
            keyboard = [[InlineKeyboardButton("✅ ثبت نهایی", callback_data="final_submit")]]
            await query.message.reply_text(QUESTIONS[current_q], reply_markup=InlineKeyboardMarkup(keyboard))
            return STEP_QUESTIONS

    elif query.data == "prev_q" and current_q > 0:
        context.user_data["current_q"] -= 1

    # دکمه‌های ناوبری
    nav_buttons = []
    if context.user_data["current_q"] > 0:
        nav_buttons.append(InlineKeyboardButton("⬅ سوال قبل", callback_data="prev_q"))
    if context.user_data["current_q"] < len(QUESTIONS) - 1:
        nav_buttons.append(InlineKeyboardButton("سوال بعد ➡", callback_data="next_q"))
    else:
        nav_buttons.append(InlineKeyboardButton("✅ ثبت نهایی", callback_data="final_submit"))

    await query.message.reply_text(
        QUESTIONS[context.user_data["current_q"]],
        reply_markup=InlineKeyboardMarkup([nav_buttons])
    )
    return STEP_QUESTIONS

async def final_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت نهایی پاسخ‌ها در Google Sheet"""
    query = update.callback_query
    await query.answer()

    name = context.user_data.get("name", "")
    selected_number = context.user_data.get("selected_number", "")
    answers = context.user_data.get("answers", [])

    # اضافه کردن داده‌ها به شیت
    sheet.append_row([name, selected_number] + answers)

    await query.message.reply_photo(
        photo="https://chandeen.ir/wp-content/uploads/2025/08/image3.jpg",
        caption="اطلاعات شما با موفقیت ثبت شد 🙏"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

# ---------------- Main App ----------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_button, pattern="^start$")
        ],
        states={
            STEP_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
            ],
            STEP_SELECT_NUMBER: [
                CallbackQueryHandler(select_number, pattern="^num_")
            ],
            STEP_QUESTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer),
                CallbackQueryHandler(navigate_question, pattern="^(prev_q|next_q)$"),
                CallbackQueryHandler(final_submit, pattern="^final_submit$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.run_polling()
