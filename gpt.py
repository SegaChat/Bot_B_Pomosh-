import requests
import logging

from config import *
from info import SYSTEM_PROMPT, CONTINUE_STORY, END_STORY

logging.basicConfig(filename=LOGS_PATH,
                    level=logging.DEBUG,
                    format="%(asctime)s %(message)s",
                    filemode="w")

def count_tokens(text): 
    """Подсчитывает количество токенов в сообщении."""
    headers = {
        'Authorization': f'Bearer {IAM_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
       "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
       "text": text,
    }
    try:
        response = requests.post(
            url="https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize",
            json=data,
            headers=headers
        )
        response.raise_for_status()
        return len(response.json()["tokens"])
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при подсчете токенов: {e}")
        return 0

def create_prompt(user_data):
    prompt = SYSTEM_PROMPT
    prompt += (f"\nНапиши начало истории в стиле {user_data['genre']} "
              f"с главным героем {user_data['character']}. "
              f"Вот начальный сеттинг: \n{user_data['setting']}. \n"
              "Начало должно быть коротким, 1-3 предложения.\n")

    prompt += 'Не пиши никакие подсказки пользователю, что делать дальше. Он сам знает'

    return prompt

def ask_gpt(collection, mode='continue'):
    """Запрос к Yandex GPT"""
    url = f"https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        'Authorization': f'Bearer {IAM_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/{GPT_MODEL}/latest",
        "completionOptions": {
            "stream": False,
            "temperature": MODEL_TEMPERATURE,
            "maxTokens": MAX_MODEL_TOKENS
        },
        "messages": []
    }

    for row in collection:
        content = row['content']
        if mode == 'continue' and row['role'] == 'user':
            content += '\n' + CONTINUE_STORY
        elif mode == 'end' and row['role'] == 'user':
            content += '\n' + END_STORY

        data["messages"].append(
                {
                    "role": row["role"],
                    "text": content
                }
            )
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()['result']['alternatives'][0]['message']['text']
        return result
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к GPT: {e}")
        return "Произошла ошибка при обращении к GPT. Подробности см. в журнале."
