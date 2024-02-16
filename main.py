import telebot
from googletrans import Translator
import wikipedia
from telebot import types
from datetime import datetime
from decouple import config
import json
import time

BOT_TOKEN = config('BOT_TOKEN')
wikipedia.set_lang("uz")

bot = telebot.TeleBot(BOT_TOKEN)

search_history = {}
MAX_QUERY_LENGTH = 300


@bot.message_handler(commands=['start'])
def handle_start(message):
    response = "Hello! I will retrieve information from Wikipedia based on your query."
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['history'])
def handle_history(message):
    user_id = message.from_user.id
    if user_id in search_history and search_history[user_id]:
        history_text = "\n".join(search_history[user_id])
        response = f"User's search history:\n{history_text}"
        keyboard = types.InlineKeyboardMarkup()
        button_clear_history = types.InlineKeyboardButton(text='Clear History', callback_data='clear_history')
        button_clear_last_search = types.InlineKeyboardButton(text='Clear Last Search', callback_data='clear_last_search')
        keyboard.add(button_clear_history, button_clear_last_search)
        bot.send_message(message.chat.id, response, reply_markup=keyboard, parse_mode='Markdown')
    else:
        response = "User has not performed any searches yet✖️"
        bot.send_message(message.chat.id, response)

def send_wikipedia_message(message, bot, keyboard, chunk):
    try:
        chunk_size = 4096
        chunks = [chunk[i:i + chunk_size] for i in range(0, len(chunk), chunk_size)]

        for sub_chunk in chunks:
            bot.send_message(message.chat.id, f"`{sub_chunk}`", reply_markup=keyboard, parse_mode='Markdown')
            log_search_history(message.from_user.id, f"`{message.text}` |✔️")
            time.sleep(1)

    except telebot.apihelper.ApiTelegramException as e:
        if e.result.status_code == 429:
            retry_after = e.result.json()['parameters']['retry_after']
            print(f"Rate limited. Retrying after {retry_after} seconds.")
            time.sleep(retry_after)
            send_wikipedia_message(message, bot, keyboard, chunk)
        else:
            print(f"Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        query = message.text[:MAX_QUERY_LENGTH]
        search_result = wikipedia.summary(query)
        search_result = wikipedia.summary(message.text)
        keyboard = types.InlineKeyboardMarkup()
        button_eng = types.InlineKeyboardButton(text='English', callback_data='en')
        button_rus = types.InlineKeyboardButton(text='Russian', callback_data='ru')
        button_uzb = types.InlineKeyboardButton(text='Uzbek', callback_data='uz')
        keyboard.add(button_eng, button_rus, button_uzb)

        chunk_size = 4000
        chunks = [search_result[i:i + chunk_size] for i in range(0, len(search_result), chunk_size)]

        for chunk in chunks:
            send_wikipedia_message(message, bot, keyboard, chunk)

    except wikipedia.exceptions.DisambiguationError as e:
        response = "Couldn't find the required information. Please submit another query."
        bot.send_message(message.chat.id, response)
        log_search_history(message.from_user.id, f"`{message.text}` |✖️")
    except wikipedia.exceptions.PageError as e:
        response = "Couldn't find information for this query. Please submit another query."
        bot.send_message(message.chat.id, response)
        log_search_history(message.from_user.id, f"`{message.text}` |✖️")
    except json.decoder.JSONDecodeError:
        response = "Information from Wikipedia is not in JSON format. Please submit another query."
        bot.send_message(message.chat.id, response)
        log_search_history(message.from_user.id, f"`{message.text}` |✖️")
    except wikipedia.exceptions.WikipediaException as e:
        error_message = f"Wikipedia API error: {str(e)}"
        bot.send_message(message.chat.id, error_message)
        log_search_history(message.from_user.id, f"`{message.text}` |✖️")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.message:
        user_id = call.from_user.id
        translator = Translator()
        if call.data == 'en':
            translation = translator.translate(call.message.text, src='uz', dest='en').text
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"`{translation}`", parse_mode='Markdown')
        elif call.data == 'ru':
            translation = translator.translate(call.message.text, src='uz', dest='ru').text
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"`{translation}`", parse_mode='Markdown')
        elif call.data == 'uz':
            translation = call.message.text
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"`{translation}`", parse_mode='Markdown')
        elif call.data == 'clear_history':
            search_history[user_id] = []
            bot.send_message(call.message.chat.id, "User's search history has been cleared✔️")
            user_id = call.from_user.id
            response = "User has not performed any searches yet✖️"
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=response)
        elif call.data == 'clear_last_search':
            if user_id in search_history and search_history[user_id]:
                del search_history[user_id][-1]
                bot.send_message(call.message.chat.id, "Last searched information has been deleted✔️")
            else:
                bot.send_message(call.message.chat.id, "User has not performed any searches yet✖️")
            keyboard = types.InlineKeyboardMarkup()
            button_clear_history = types.InlineKeyboardButton(text='Clear History', callback_data='clear_history')
            button_clear_last_search = types.InlineKeyboardButton(text='Clear Last Search', callback_data='clear_last_search')
            keyboard.add(button_clear_history, button_clear_last_search)
            user_id = call.from_user.id
            if user_id in search_history and search_history[user_id]:
                history_text = "\n".join(search_history[user_id])
                response = f"User's search history:\n{history_text}"
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=response, reply_markup=keyboard, parse_mode='Markdown')
            else:
                response = "User has not performed any searches yet✖️"
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=response)

def log_search_history(user_id, query):
    if user_id not in search_history:
        search_history[user_id] = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    search_history[user_id].append(f"{current_time}: {query}")

bot.polling(none_stop=True)