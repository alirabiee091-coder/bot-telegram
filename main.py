import os
import json
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# مراحل گفتگو
STEP_NAME, STEP_SELECT_NUMBER, STEP_QUESTIONS = range(3)

QUESTIONS = [
    "سوال اول رو پاسخ میده؟",
    "سوال دوم رو پاسخ میده؟",
    "سوال سوم رو پاسخ میده؟",
    "سوال چهارم رو پاسخ میده؟"
]

IMAGE1 = "https://chandeen.ir/wp-content/uploads/2025/08/image1.jpg"
IMAGE2 = "https://chandeen.ir/wp-content/uploads/2025/08/image2.jpg"
IMAGE3 = "https://chandeen.ir/wp-content/uploads/2025/08/image3.jpg"

# اتصال به Google Sheets با Environment Variable
scope = ["https://www.googleapis.com/auth/spreadsheets"]
service_account_info = json.loads(os.environ["GOOGLE_SA_KEY"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(os.environ.get("SPREADSHEET_ID"))
sheet = spreadsheet.sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("شروع", callback_data="start")]]
    await update.message.reply_photo(IMAGE1, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.WAITING

async def start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("نام و نام خانوادگی خود را وارد کنید:")
    return STEP_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    keyboard_numbers = [
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(1, 4)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(4, 7)],
        [InlineKeyboardButton(str(i), callback_data=f"num_{i}") for i in range(7, 10)]
    ]
    await update.message.reply_photo(
        IMAGE2,
        reply_markup=InlineKeyboardMarkup(keyboard_numbers)
    )
    return STEP_SELECT_NUMBER

async def select_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['number'] = query.data.split("_")[1]
    context.user_data['answers'] = [""] * len(QUESTIONS)
    context.user_data['q_index'] = 0
    await send_question(query.message.chat_id, context)
    return STEP_QUESTIONS

async def send_question(chat_id, context: ContextTypes.DEFAULT_TYPE):
    q_index = context.user_data['q_index']
    buttons = []
    if q_index > 0:
        buttons.append(InlineKeyboardButton("⬅️ سوال قبل", callback_data="prev_q"))
    if q_index < len(QUESTIONS) - 1:
        buttons.append(InlineKeyboardButton("سوال بعد ➡️", callback_data="next_q"))
    else:
        buttons.append(InlineKeyboardButton("ثبت نهایی ✅", callback_data="final_submit"))
    await context.bot.send_message(
        chat_id=chat_id,
        text=QUESTIONS[q_index],
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q_index = context.user_data['q_index']
    context.user_data['answers'][q_index] = update.message.text.strip()
    return await send_question(update.message.chat_id, context)

async def navigate_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "prev_q":
        context.user_data['q_index'] -= 1
    elif query.data == "next_q":
        context.user_data['q_index'] += 1
    return await send_question(query.message.chat_id, context)

async def final_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # ذخیره در Google Sheet
    sheet.append_row([
        context.user_data['name'],
        context.user_data['number'],
        *context.user_data['answers']
    ])
    await query.message.reply_photo(IMAGE3, caption="✅ اطلاعات شما با موفقیت ثبت شد.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ گفتگو لغو شد.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(os.environ.get("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            STEP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            STEP_SELECT_NUMBER: [CallbackQueryHandler(select_number, pattern="^num_")],
            STEP_QUESTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer),
                CallbackQueryHandler(navigate_question, pattern="^(prev_q|next_q)$"),
                CallbackQueryHandler(final_submit, pattern="^final_submit$")
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    app.add_handler(CallbackQueryHandler(start_button, pattern="^start$"))
    app.add_handler(conv_handler)
    app.run_polling()
