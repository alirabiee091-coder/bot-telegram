
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# مراحل گفتگو
STEP_NAME, STEP_SELECT_NUMBER, STEP_QUESTION = range(3)

# اتصال به Google Sheet با استفاده از Environment Variable
import json

scope = ["https://www.googleapis.com/auth/spreadsheets"]
service_account_info = json.loads(os.environ["GOOGLE_SA_KEY"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)

spreadsheet = client.open_by_key(os.environ.get("SPREADSHEET_ID"))
sheet = spreadsheet.sheet1

QUESTIONS = [
    "سوال ۱: چه رنگی رو دوست داری؟",
    "سوال ۲: غذای مورد علاقت چیه؟",
    "سوال ۳: شهر مورد علاقه‌ات کجاست؟"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لطفاً اسم خودت رو بگو.")
    return STEP_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=str(i)) for i in range(1, 6)]
    ]
    await update.message.reply_text(
        "یک شماره انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STEP_SELECT_NUMBER

async def select_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['number'] = query.data
    context.user_data['answers'] = []
    await query.edit_message_text(QUESTIONS[0])
    context.user_data['q_index'] = 0
    return STEP_QUESTION

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['answers'].append(update.message.text)
    q_index = context.user_data['q_index'] + 1
    if q_index < len(QUESTIONS):
        context.user_data['q_index'] = q_index
        await update.message.reply_text(QUESTIONS[q_index])
        return STEP_QUESTION
    else:
        # ذخیره داده‌ها در Google Sheet
        sheet.append_row([
            context.user_data['name'],
            context.user_data['number'],
            *context.user_data['answers']
        ])
        await update.message.reply_text("ممنون! اطلاعاتت ذخیره شد.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("گفتگو لغو شد.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(os.environ.get("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            STEP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            STEP_SELECT_NUMBER: [CallbackQueryHandler(select_number)],
            STEP_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    app.run_polling()
