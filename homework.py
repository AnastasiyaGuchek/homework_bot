import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PREVIOUS_HOMEWORK_TIME_JSON = 1664843799

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log'
)
logger = logging.getLogger('app_logger')
std_format = logging.Formatter(
    fmt='{asctime} - {levelname} - {name} - {message}',
    style='{'
)

console_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(console_handler)
console_handler.setFormatter(std_format)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    TOKENS = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(TOKENS)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug('Сообщение отправлено.')
    except Exception:
        logger.error('Сообщение не отправлено.')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        logger.info('Запрос на сервер отправлен.')
    except Exception:
        logger.error('Запрос на сервер не отправлен.')
    if response.status_code != HTTPStatus.OK:
        raise logger.error('Не удалось получить ответ API'
                           f'error-status: {response.status_code}.')
    try:
        return response.json()
    except Exception:
        raise logger.error('Ответ от сервера не в json формате.')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ на запрос не является словарем.')
    if 'homeworks' not in response:
        logger.error('В ответе API нет ключа homeworks.')
        raise KeyError('В ответе API нет ключа homeworks.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не является списком.')
    return homeworks[0]


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API нет ключа homework_name.')
    if 'status' not in homework:
        raise KeyError('В ответе API нет ключа status.')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус работы - {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутсвует переменная окружения.')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    previous_homework_time = PREVIOUS_HOMEWORK_TIME_JSON
    STATUS = ''

    while True:
        try:
            response = get_api_answer(previous_homework_time)
            new_status = parse_status(check_response(response))
            if new_status != STATUS:
                send_message(bot, new_status)
                if STATUS != '':
                    previous_homework_time = int(time.time())
                STATUS = new_status
            else:
                logger.debug('Статус домашней работы не изменился.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logger.error(message)
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
