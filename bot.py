import logging
import os.path
import telebot
from telebot import types
from config import TOKEN, LOGS_PATH, Creater_ID, MAX_USERS, MAX_TOKENS_IN_SESSION, MAX_SESSIONS
from gpt import ask_gpt, create_prompt, count_tokens
from info import genres, characters, settings

TOKEN = '6790954372:AAH_oaCFd_f-iZoAAd0OtSZG1SXJ6OyNsb4'

logging.basicConfig(
    filename=LOGS_PATH,
    level=logging.DEBUG,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    filemode="w"
)

bot = telebot.TeleBot(TOKEN)

user_data = {}
user_collection = {}

def menu_keyboard(options):
    """Создаёт клавиатуру с указанными кнопками."""
    buttons = (types.KeyboardButton(text=option) for option in options)
    keyboard = types.ReplyKeyboardMarkup(
        row_width=2,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    keyboard.add(*buttons)
    return keyboard

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start."""
    user_name = message.from_user.first_name
    user_id = message.from_user.id

    user_collection[user_id] = []

    if not user_data.get(user_id):
        user_data[user_id] = {
            'session_id': 0,
            'genre': None,
            'character': None,
            'setting': None,
            'state': 'регистрация',
            'session_tokens': 0
        }

    bot.send_message(message.chat.id, f"Привет, {user_name}! Я бот, который создаёт истории с помощью нейросети.\n"
                                      f"Мы будем писать историю поочерёдно. Я начну, а ты продолжить.\n"
                                      "Напиши /new_story, чтобы начать новую историю.\n"
                                      f"А когда ты закончишь, напиши /end.",
                     reply_markup=menu_keyboard(["/new_story"]))


@bot.message_handler(commands=['begin'])
def begin_story(message):
    """Обработчик команды /begin."""
    user_id = message.from_user.id
    if user_id not in user_data or user_data[user_id]['state'] == 'регистрация':
        bot.send_message(message.chat.id, "Прежде чем начать писать историю, нужно допройти регистрацию -> /new_story")
        return

    user_data[user_id]['state'] = 'в истории'
    get_story(message)



@bot.message_handler(commands=['debug'])
def send_logs(message):
    if message.from_user.id == Creater_ID:
        if os.path.exists(LOGS_PATH):
            bot.send_document(message.chat.id, open(LOGS_PATH, 'rb'))
        else:
            bot.send_message(message.chat.id, "Файл с логами не найден, увы.")


@bot.message_handler(commands=['end'])
def end_the_story(message):
    user_id = message.from_user.id
    if user_id not in user_collection:
        bot.send_message(message.chat.id, "Вы ещё не начали историю. Начните с /begin.")
        return

    gpt_text = ask_gpt(user_collection[user_id], mode='end')
    bot.send_message(message.chat.id, gpt_text, reply_markup=menu_keyboard(["/new_story", "/debug"]))
    user_collection[user_id] = []
    user_data[user_id]['session_tokens'] = 0
    user_data[user_id]['state'] = 'регистрация'



@bot.message_handler(commands=['new_story'])
def registration(message):
    users_amount = len(user_data)
    if users_amount > MAX_USERS:
        bot.send_message(message.chat.id, 'Лимит пользователей для регистрации превышен')
        return

    bot.send_message(message.chat.id, "Выбери жанр истории:", reply_markup=menu_keyboard(genres))
    bot.register_next_step_handler(message, handle_genre)



def handle_genre(message):
    """Записывает ответ на вопрос о жанре и отправляет следующий вопрос о персонаже."""
    user_id = message.from_user.id
    genre = message.text
    if genre not in genres:
        bot.send_message(message.chat.id, "Выбери один из предложенных на клавиатуре жанров:",
                         reply_markup=menu_keyboard(genres))
        bot.register_next_step_handler(message, handle_genre)
        return
    user_data[user_id]['genre'] = genre
    user_data[user_id]['state'] = 'в истории'
    bot.send_message(message.chat.id, "Выбери главного героя:",
                     reply_markup=menu_keyboard(characters))
    bot.register_next_step_handler(message, handle_character)


def handle_character(message):
    user_id = message.from_user.id
    character = message.text
    if character not in characters:
        bot.send_message(message.chat.id, "Выбери один из предложенных на клавиатуре персонажей:", reply_markup=menu_keyboard(characters))
        bot.register_next_step_handler(message, handle_character)
        return
    user_data[user_id]['character'] = character
    bot.send_message(message.chat.id, "Выбери сеттинг:", reply_markup=menu_keyboard(settings))
    bot.register_next_step_handler(message, handle_setting)



def handle_setting(message):
    user_id = message.from_user.id
    setting = message.text
    if setting not in settings:
        bot.send_message(message.chat.id, "Выбери один из предложенных на клавиатуре сеттингов:", reply_markup=menu_keyboard(settings))
        bot.register_next_step_handler(message, handle_setting)
        return
    user_data[user_id]['setting'] = setting
    user_data[user_id]['state'] = 'регистрация пройдена'
    bot.send_message(message.chat.id, "Можешь переходить к истории написав /begin.", reply_markup=menu_keyboard(["/begin"]))



@bot.message_handler(content_types=['text'])
def story_handler(message):
    """
    Эта функция работает до тех пор, пока пользователь не нажмет кнопку "/end"
    или не выйдет за лимиты токенов в сессии. Все ответные сообщения пользователя будут попадать
    в эту же функцию благодаря декоратору "message_handler(content_types=['text'])"
    """
    user_id = message.from_user.id
    user_answer = message.text

    user_collection[user_id].append({'role': 'user', 'content': user_answer})

    tokens_in_user_answer = count_tokens(user_answer)

    user_data[user_id]['session_tokens'] += tokens_in_user_answer

    tokens = 0
    for row in user_collection[user_id]:
        tokens += count_tokens(row['content'])

    user_data[user_id]['session_tokens'] += tokens

    if user_data[user_id]['session_tokens'] > MAX_TOKENS_IN_SESSION:
        bot.send_message(
            message.chat.id,
            'В рамках данной темы вы вышли за лимит вопросов.\nМожете начать новую сессию, введя new_story',
            reply_markup=menu_keyboard(["/new_story", "/end"])
        )
        return

    gpt_text = ask_gpt(user_collection[user_id])
    user_collection[user_id].append({'role': 'assistant', 'content': gpt_text})

    tokens_in_gpt_answer = count_tokens(gpt_text)
    user_data[user_id]['session_tokens'] += tokens_in_gpt_answer

    bot.send_message(message.chat.id, gpt_text, reply_markup=menu_keyboard(['/end']))


def get_story(message):
    """
    Обработчик для генерирования начала истории.
    Эта функция отрабатывает один раз за сессию.
    """
    user_id = message.from_user.id
    user_data[user_id]['session_id'] += 1

    if user_data[user_id]['session_id'] > MAX_SESSIONS:
        bot.send_message(
            user_id,
            'К сожалению, Вы израсходовали лимит сессий 😢\nПриходите позже)'
        )
        return

    user_story = create_prompt(user_data[user_id])

    user_collection[user_id].append({'role': 'system', 'content': user_story})
    tokens_for_start_story = count_tokens(user_story)

    user_data[user_id]['session_tokens'] += tokens_for_start_story

    bot.send_message(message.chat.id, "Генерирую...")

    gpt_text = ask_gpt(user_collection[user_id])
    user_collection[user_id].append({'role': 'assistant', 'content': gpt_text})
    tokens_in_gpt_answer = count_tokens(gpt_text)

    user_data[user_id]['session_tokens'] += tokens_in_gpt_answer

    if user_data[user_id]['session_tokens'] > MAX_TOKENS_IN_SESSION:
        bot.send_message(
            message.chat.id,
            'В рамках данной темы вы вышли за лимит вопросов.\nМожете начать новую сессию, введя new_story',
            reply_markup=menu_keyboard(["/new_story", "/end"])
        )
        return

    if gpt_text is None:
        bot.send_message(
            message.chat.id,
            "Не могу получить ответ от GPT :(",
            reply_markup=menu_keyboard(["/new_story", "/end"])
        )

    elif gpt_text == "":
        bot.send_message(
            message.chat.id,
            "Не могу сформулировать решение :(",
            reply_markup=menu_keyboard(["/new_story", "/end"])
        )
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: нейросеть вернула пустую строку")

    else:
        msg = bot.send_message(message.chat.id, gpt_text)
        bot.register_next_step_handler(msg, story_handler)


bot.infinity_polling()
