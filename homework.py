import logging
import os
import sys
import time

import requests
import telebot
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, [%(levelname)s] %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет токены для работы бота."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    missing_tokens = []
    for key, value in tokens.items():
        if not value:
            missing_tokens.append(key)

    if missing_tokens:
        missing_tokens_str = ', '.join(missing_tokens)
        logger.critical(f'Отсутствуют токены для бота: {missing_tokens_str}')
        sys.exit()


def send_message(bot, message):
    """Отправляет сообщение боту."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Успешно отправленно сообщение: {message}')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения:  {error}')


def get_api_answer(timestamp):
    """Делает запрос к API-сервису."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка запроса к API: {error}, параметры: {payload}')
        return None
    if response.status_code != requests.codes.ok:
        raise requests.HTTPError(f'Вернулся HTTP-код: {response.status_code}')
    try:
        return response.json()
    except ValueError as error:
        logging.error(f'Ошибка парсинга JSON: {error}')
        return None


def check_response(response):
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем')

    if 'homeworks' not in response:
        raise KeyError('Ответ API не содержит ключ "homeworks"')

    if 'current_date' not in response:
        raise KeyError('Ответ API не содержит ключ "current_date"')

    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение "homeworks" должно быть списком')

    logger.debug('Данные в ответе от сервера ОК')
    return response


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    if not isinstance(homework, dict):
        raise TypeError('Аргумент "homework" должен быть словарем')

    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ "homework_name"')

    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ "status"')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус домашней работы: {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            response = check_response(response)
            homeworks = response.get('homeworks')
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logger.info('Новых статусов нет.')
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
