import os
import logging
from flask import Flask, request, jsonify
import requests
from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    exit(1)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Список поддерживаемых языков
LANGUAGE_EMOJIS = {
    'en': '🇺🇸', 'ru': '🇷🇺', 'es': '🇪🇸', 'fr': '🇫🇷', 'de': '🇩🇪',
    'it': '🇮🇹', 'pt': '🇵🇹', 'zh-cn': '🇨🇳', 'ja': '🇯🇵', 'ko': '🇰🇷',
    'ar': '🇸🇦', 'tr': '🇹🇷', 'hi': '🇮🇳', 'uk': '🇺🇦'
}

SUPPORTED_LANGUAGES = {
    'en': 'English', 'ru': 'Russian', 'es': 'Spanish', 'fr': 'French',
    'de': 'German', 'it': 'Italian', 'pt': 'Portuguese', 'zh-cn': 'Chinese',
    'ja': 'Japanese', 'ko': 'Korean', 'ar': 'Arabic', 'tr': 'Turkish',
    'hi': 'Hindi', 'uk': 'Ukrainian'
}

def setup_webhook():
    """Автоматическая настройка webhook при запуске"""
    try:
        # Получаем URL приложения из переменных окружения Render
        app_url = os.environ.get('RENDER_EXTERNAL_URL')
        if not app_url:
            logger.warning("❌ RENDER_EXTERNAL_URL не установлен, webhook не настроен")
            return False
        
        webhook_url = f"{app_url}/webhook"
        response = requests.get(f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}")
        
        if response.json().get('ok'):
            logger.info(f"✅ Webhook установлен: {webhook_url}")
            return True
        else:
            logger.error(f"❌ Ошибка настройки webhook: {response.json()}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка настройки webhook: {e}")
        return False

def send_telegram_message(chat_id, text, parse_mode='HTML'):
    """Отправка сообщения в Telegram"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def detect_language_simple(text):
    """Простое определение языка"""
    try:
        return detect(text)
    except LangDetectException:
        if any('\u0400' <= char <= '\u04FF' for char in text):
            return 'ru'
        else:
            return 'en'

@app.route('/')
def index():
    app_url = os.environ.get('RENDER_EXTERNAL_URL', 'Unknown')
    return jsonify({
        "status": "✅ Telegram Translator Bot is running!",
        "webhook_url": f"{app_url}/webhook",
        "instructions": "Send /start to your bot in Telegram"
    })

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Webhook endpoint для Telegram"""
    if request.method == 'GET':
        return "✅ Webhook is ready for POST requests from Telegram"
    
    try:
        data = request.get_json()
        logger.info(f"Received update: {data}")
        
        if 'message' in data and 'text' in data['message']:
            message = data['message']
            chat_id = message['chat']['id']
            text = message['text'].strip()
            
            # Обрабатываем команды
            if text.startswith('/'):
                if text == '/start' or text.startswith('/start'):
                    welcome_text = """
🤖 <b>Telegram Translator Bot</b>

🎯 <b>Как использовать:</b>
• Просто напиши сообщение - переведу на несколько языков
• Или укажи язык: <code>текст /язык</code>
• Пример: <code>Hello world /ru</code>

📋 <b>Команды:</b>
/lang - список языков
/help - помощь

🌍 <b>Поддержка 15+ языков!</b>
                    """
                    send_telegram_message(chat_id, welcome_text)
                
                elif text == '/lang' or text.startswith('/lang'):
                    langs_text = "🌍 <b>Поддерживаемые языки:</b>\n\n"
                    for code, name in SUPPORTED_LANGUAGES.items():
                        emoji = LANGUAGE_EMOJIS.get(code, '🌐')
                        langs_text += f"{emoji} <code>{code}</code> - {name}\n"
                    send_telegram_message(chat_id, langs_text)
                
                elif text == '/help' or text.startswith('/help'):
                    help_text = """
📖 <b>Помощь по использованию</b>

🚀 <b>Автоматический перевод:</b>
Напиши любое сообщение - бот определит язык и переведет на английский, русский и испанский

🎯 <b>Ручной перевод:</b>
<code>текст /язык</code> - перевод на конкретный язык
Пример: <code>Bonjour /en</code> → Hello

🔧 <b>Команды:</b>
/lang - список всех языков
/help - эта справка
                    """
                    send_telegram_message(chat_id, help_text)
                else:
                    send_telegram_message(chat_id, "❌ Неизвестная команда. Используйте /help для справки")
            
            else:
                # Обрабатываем обычные сообщения для перевода
                handle_translation(chat_id, text)
        
        return 'OK'
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

def handle_translation(chat_id, text):
    """Обработка перевода"""
    try:
        # Проверяем формат "текст /язык"
        if ' /' in text and len(text.split(' /')) == 2:
            parts = text.split(' /')
            original_text = parts[0].strip()
            target_lang = parts[1].strip().lower()
            
            if original_text and target_lang in SUPPORTED_LANGUAGES:
                # Перевод на конкретный язык
                translation = GoogleTranslator(source='auto', target=target_lang).translate(original_text)
                response = f"""
🌐 <b>Исходный текст:</b>
{original_text}

{LANGUAGE_EMOJIS.get(target_lang, '🌐')} <b>Перевод ({SUPPORTED_LANGUAGES[target_lang]}):</b>
{translation}
                """
                send_telegram_message(chat_id, response)
                return
        
        # Автоматический перевод на несколько языков
        source_lang = detect_language_simple(text)
        source_lang_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
        
        # Языки для перевода (исключаем исходный)
        target_languages = ['en', 'ru', 'es']
        target_languages = [lang for lang in target_languages if lang != source_lang]
        
        if not target_languages:
            target_languages = ['en', 'ru']
        
        response = f"🌐 <b>Обнаружен язык:</b> {source_lang_name}\n"
        response += f"<b>Исходный текст:</b>\n{text}\n\n"
        response += "<b>Переводы:</b>\n\n"
        
        successful_translations = 0
        
        for target_lang in target_languages[:3]:
            try:
                translation = GoogleTranslator(source='auto', target=target_lang).translate(text)
                emoji = LANGUAGE_EMOJIS.get(target_lang, '🌐')
                response += f"{emoji} <b>{SUPPORTED_LANGUAGES[target_lang]}:</b>\n{translation}\n\n"
                successful_translations += 1
            except Exception as e:
                logger.error(f"Translation error for {target_lang}: {e}")
                continue
        
        if successful_translations > 0:
            response += "---\n"
            response += "💡 <i>Для перевода на конкретный язык: текст /язык</i>\n"
            response += "🔧 <i>Список языков: /lang</i>"
            send_telegram_message(chat_id, response)
        else:
            send_telegram_message(chat_id, "❌ Не удалось выполнить перевод")
    
    except Exception as e:
        logger.error(f"Translation handling error: {e}")
        send_telegram_message(chat_id, "❌ Произошла ошибка при переводе")

@app.route('/set_webhook', methods=['GET'])
def set_webhook_manual():
    """Ручная установка webhook"""
    app_url = os.environ.get('RENDER_EXTERNAL_URL')
    if not app_url:
        return "❌ RENDER_EXTERNAL_URL не установлен"
    
    webhook_url = f"{app_url}/webhook"
    try:
        response = requests.get(f"{TELEGRAM_API_URL}/setWebhook?url={webhook_url}")
        if response.json().get('ok'):
            return f"✅ Webhook установлен: {webhook_url}"
        else:
            return f"❌ Ошибка: {response.json()}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

@app.route('/get_webhook_info', methods=['GET'])
def get_webhook_info():
    """Получить информацию о webhook"""
    try:
        response = requests.get(f"{TELEGRAM_API_URL}/getWebhookInfo")
        return jsonify(response.json())
    except Exception as e:
        return f"❌ Ошибка: {e}"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

# Автоматическая настройка webhook при импорте
if os.environ.get('RENDER'):
    setup_webhook()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting bot on port {port}")
    
    # Настраиваем webhook при запуске
    if os.environ.get('RENDER_EXTERNAL_URL'):
        setup_webhook()
    
    app.run(host='0.0.0.0', port=port, debug=False)
