import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import NegativeResponseError


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
        logging.debug('Сообщение отправлено.')
    except Exception:
        logging.error('Сообщение не отправлено.')


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
        logging.info('Запрос на сервер отправлен.')
    except Exception as error:
        raise NegativeResponseError(f'Запрос на сервер не отправлен. {error}.')

    if response.status_code != HTTPStatus.OK:
        raise logging.error('Не удалось получить ответ API'
                            f'error-status: {response.status_code}.')
    try:
        return response.json()
    except Exception:
        raise logging.error('Ответ от сервера не в json формате.')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ на запрос не является словарем.')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа homeworks.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не является списком.')
    try:
        homework = homeworks[0]
    except IndexError:
        raise IndexError('Список домашних работ пуст.')
    return homework


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
    status = ''
    current_timestamp = int(time.time())

    if not get_api_answer(current_timestamp):
        logging.error('Запрос на сервер не отправлен.')

    while True:
        try:
            response = get_api_answer(previous_homework_time)
            new_status = parse_status(check_response(response))
            if new_status != status:
                send_message(bot, new_status)
                if status != '':
                    previous_homework_time = int(time.time())
                status = new_status
            else:
                logging.debug('Статус домашней работы не изменился.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logging.error(message)
            send_message(bot, message)
        try:
            get_api_answer(response)
        except KeyError as error:
            message = f'В ответе API нет ключа homeworks. {error}.'
            logging.error(message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='program.log'
    )
    logger = logging.getLogger('app_logger')
    logger.setLevel(logging.DEBUG)
    std_format = logging.Formatter(
        '{asctime} - {levelname} - {name} - {message} - {funcName} - {lineno}',
        style='{'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(console_handler)
    console_handler.setFormatter(std_format)

    main()
