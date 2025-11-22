import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
from langdetect import detect, detect_langs, LangDetectException

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

app = Flask(__name__)

# Получаем токен из переменных окружения Render
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')

if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN не установлен!")
    exit(1)

# Список поддерживаемых языков с эмодзи
LANGUAGE_EMOJIS = {
    'en': '🇺🇸', 'ru': '🇷🇺', 'es': '🇪🇸', 'fr': '🇫🇷', 'de': '🇩🇪',
    'it': '🇮🇹', 'pt': '🇵🇹', 'zh-cn': '🇨🇳', 'ja': '🇯🇵', 'ko': '🇰🇷',
    'ar': '🇸🇦', 'tr': '🇹🇷', 'hi': '🇮🇳', 'uk': '🇺🇦', 'pl': '🇵🇱',
    'nl': '🇳🇱', 'sv': '🇸🇪', 'no': '🇳🇴', 'da': '🇩🇰', 'fi': '🇫🇮',
    'cs': '🇨🇿', 'sk': '🇸🇰', 'hu': '🇭🇺', 'ro': '🇷🇴', 'bg': '🇧🇬',
    'el': '🇬🇷', 'he': '🇮🇱', 'id': '🇮🇩', 'th': '🇹🇭', 'vi': '🇻🇳'
}

SUPPORTED_LANGUAGES = {
    'en': 'English',
    'ru': 'Russian', 
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'zh-cn': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
    'ar': 'Arabic',
    'tr': 'Turkish',
    'hi': 'Hindi',
    'uk': 'Ukrainian',
    'pl': 'Polish',
    'nl': 'Dutch',
    'sv': 'Swedish',
    'no': 'Norwegian',
    'da': 'Danish',
    'fi': 'Finnish',
    'cs': 'Czech',
    'sk': 'Slovak',
    'hu': 'Hungarian',
    'ro': 'Romanian',
    'bg': 'Bulgarian',
    'el': 'Greek',
    'he': 'Hebrew',
    'id': 'Indonesian',
    'th': 'Thai',
    'vi': 'Vietnamese'
}

DEFAULT_TARGET_LANGUAGES = ['en', 'ru', 'es', 'fr', 'de']

# Глобальная переменная для приложения
application = None

def detect_language_advanced(text):
    """Улучшенное определение языка с использованием langdetect"""
    try:
        if len(text.strip()) < 3:
            return detect_language_simple(text)
        
        languages = detect_langs(text)
        best_lang = str(languages[0]).split(':')[0]
        
        if best_lang in SUPPORTED_LANGUAGES:
            return best_lang
        else:
            for lang_prob in languages:
                lang_code = str(lang_prob).split(':')[0]
                if lang_code in SUPPORTED_LANGUAGES:
                    return lang_code
            return detect_language_simple(text)
            
    except LangDetectException:
        return detect_language_simple(text)
    except Exception as e:
        logging.error(f"Language detection error: {e}")
        return detect_language_simple(text)

def detect_language_simple(text):
    """Резервное определение языка по символам"""
    cyrillic_count = 0
    latin_count = 0
    arabic_count = 0
    hebrew_count = 0
    greek_count = 0
    
    for char in text:
        if '\u0400' <= char <= '\u04FF':
            cyrillic_count += 1
        elif '\u0041' <= char <= '\u007A' or '\u00C0' <= char <= '\u00FF':
            latin_count += 1
        elif '\u0600' <= char <= '\u06FF':
            arabic_count += 1
        elif '\u0590' <= char <= '\u05FF':
            hebrew_count += 1
        elif '\u0370' <= char <= '\u03FF':
            greek_count += 1
    
    if cyrillic_count > latin_count and cyrillic_count > 0:
        return 'ru'
    elif arabic_count > 0:
        return 'ar'
    elif hebrew_count > 0:
        return 'he'
    elif greek_count > 0:
        return 'el'
    else:
        return 'en'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """
🤖 **Бот-переводчик с улучшенным определением языка**

**Возможности:**
• Автоматическое определение языка сообщения
• Перевод на несколько языков одновременно
• Высокая точность распознавания

**Как использовать:**
1. Просто напиши сообщение - бот сам определит язык и переведет
2. Или укажи язык: `текст /язык`
3. Пример: `Hello world /ru`

**Команды:**
/setlang - настроить языки перевода
/lang - список всех языков
/help - помощь
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def set_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите языки через пробел\n"
            "Пример: `/setlang en ru es fr de`",
            parse_mode='Markdown'
        )
        return
    
    valid_langs = [lang for lang in context.args if lang in SUPPORTED_LANGUAGES]
    invalid_langs = [lang for lang in context.args if lang not in SUPPORTED_LANGUAGES]
    
    if not valid_langs:
        await update.message.reply_text("❌ Не указано валидных языков")
        return
    
    chat_id = update.message.chat_id
    if 'chat_settings' not in context.bot_data:
        context.bot_data['chat_settings'] = {}
    
    context.bot_data['chat_settings'][chat_id] = {'target_languages': valid_langs}
    
    response = f"✅ Установлены языки для перевода:\n"
    for lang in valid_langs:
        emoji = LANGUAGE_EMOJIS.get(lang, '🌐')
        response += f"{emoji} {SUPPORTED_LANGUAGES[lang]}\n"
    
    if invalid_langs:
        response += f"\n❌ Неподдерживаемые языки: {', '.join(invalid_langs)}"
    
    await update.message.reply_text(response)

async def show_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список языков"""
    languages_text = "🌍 **Поддерживаемые языки:**\n\n"
    
    popular_langs = ['en', 'ru', 'es', 'fr', 'de', 'it', 'pt', 'zh-cn', 'ja', 'ko']
    other_langs = [code for code in SUPPORTED_LANGUAGES.keys() if code not in popular_langs]
    
    languages_text += "**Популярные:**\n"
    for code in popular_langs:
        emoji = LANGUAGE_EMOJIS.get(code, '🌐')
        languages_text += f"{emoji} `{code}` - {SUPPORTED_LANGUAGES[code]}\n"
    
    languages_text += "\n**Другие языки:**\n"
    for code in sorted(other_langs):
        emoji = LANGUAGE_EMOJIS.get(code, '🌐')
        languages_text += f"{emoji} `{code}` - {SUPPORTED_LANGUAGES[code]}\n"
    
    await update.message.reply_text(languages_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    help_text = """
📖 **Помощь по использованию бота-переводчика**

**Автоматический режим:**
Просто напишите любое сообщение - бот определит язык и переведет на установленные языки

**Ручной режим:**
`текст /язык` - перевод на конкретный язык
Пример: `Bonjour /en` → Hello

**Настройка:**
`/setlang en ru es` - установить языки для автоперевода
`/lang` - посмотреть все доступные языки

**Поддержка 30+ языков** с высокой точностью определения!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def auto_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    
    if text.startswith('/'):
        return
    
    if ' /' in text and len(text.split(' /')) == 2:
        parts = text.split(' /')
        original_text, target_lang = parts[0].strip(), parts[1].strip().lower()
        
        if original_text and target_lang and target_lang in SUPPORTED_LANGUAGES:
            try:
                source_lang = detect_language_advanced(original_text)
                translation = GoogleTranslator(source=source_lang, target=target_lang).translate(original_text)
                
                source_emoji = LANGUAGE_EMOJIS.get(source_lang, '🌐')
                target_emoji = LANGUAGE_EMOJIS.get(target_lang, '🌐')
                
                response = f"""
{source_emoji} **Исходный текст** ({SUPPORTED_LANGUAGES.get(source_lang, source_lang)}):
{original_text}

{target_emoji} **Перевод** ({SUPPORTED_LANGUAGES[target_lang]}):
{translation}
"""
                await update.message.reply_text(response)
                return
            except Exception as e:
                logging.error(f"Translation error: {e}")
                await update.message.reply_text("❌ Ошибка перевода")
                return
    
    try:
        source_lang = detect_language_advanced(text)
        source_lang_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
        
        chat_id = update.message.chat_id
        target_languages = DEFAULT_TARGET_LANGUAGES
        
        if ('chat_settings' in context.bot_data and 
            chat_id in context.bot_data['chat_settings']):
            target_languages = context.bot_data['chat_settings'][chat_id]['target_languages']
        
        target_languages = [lang for lang in target_languages if lang != source_lang][:4]
        
        if not target_languages:
            target_languages = ['en', 'ru', 'es']
        
        source_emoji = LANGUAGE_EMOJIS.get(source_lang, '🌐')
        response = f"{source_emoji} **Обнаружен язык**: {source_lang_name}\n"
        response += f"**Исходный текст**:\n{text}\n\n**Переводы:**\n\n"
        
        successful_translations = 0
        
        for target_lang in target_languages:
            try:
                translation = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
                target_emoji = LANGUAGE_EMOJIS.get(target_lang, '🌐')
                response += f"{target_emoji} **{SUPPORTED_LANGUAGES[target_lang]}**:\n{translation}\n\n"
                successful_translations += 1
            except Exception as e:
                logging.error(f"Error translating to {target_lang}: {e}")
                continue
        
        if successful_translations > 0:
            response += f"---\n"
            response += f"💡 *Для перевода на другой язык: текст /язык*\n"
            response += f"⚙️ *Изменить языки: /setlang*"
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Не удалось выполнить перевод на указанные языки")
        
    except Exception as e:
        logging.error(f"Auto-translate error: {e}")
        await update.message.reply_text("❌ Произошла ошибка при переводе")

def setup_bot():
    """Настройка бота"""
    global application
    
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setlang", set_languages))
    application.add_handler(CommandHandler("lang", show_languages))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_translate))
    
    return application

@app.route('/')
def index():
    return jsonify({"status": "Telegram Translator Bot is running!"})

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Webhook endpoint для Telegram"""
    if request.method == 'POST':
        try:
            json_data = request.get_json(force=True)
            update = Update.de_json(json_data, application.bot)
            await application.process_update(update)
            return 'OK'
        except Exception as e:
            logging.error(f"Webhook error: {e}")
            return 'Error', 500

@app.route('/set_webhook', methods=['GET'])
async def set_webhook():
    """Установка webhook"""
    if not WEBHOOK_URL:
        return "WEBHOOK_URL not set", 500
    
    webhook_url = f"{WEBHOOK_URL}/webhook"
    
    try:
        await application.bot.set_webhook(webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        return f"Webhook set to: {webhook_url}"
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")
        return "Failed to set webhook", 500

@app.route('/remove_webhook', methods=['GET'])
async def remove_webhook():
    """Удаление webhook"""
    try:
        await application.bot.delete_webhook()
        logging.info("Webhook removed")
        return "Webhook removed"
    except Exception as e:
        logging.error(f"Failed to remove webhook: {e}")
        return "Failed to remove webhook", 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

# Инициализируем бота
setup_bot()

if __name__ == '__main__':
    # Запускаем Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
