import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exeptions import ApiAnswerStatus, EmptyDictInResponse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format=(
        '%(asctime)s [%(levelname)s] - '
        '(%(filename)s).%(funcName)s:%(lineno)d - %(message)s'
    ),
    handlers=[
        logging.FileHandler('program.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
gif_ok = 'https://i.gifer.com/C6b.gif'
gif_fix = 'https://partnerkin.com/storage/files/file_1573820864.gif'

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщения в Telegramm."""
    logging.debug('Старт функции отправки сообщения.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение отправлено')
    except telegram.error.TelegramError as error:
        logging.error(f'Сообщение не было отправлено!!! Ошибка - {error}')


def send_animation(bot, message, gif):
    """Отправляет сообщения с анимацией в Telegramm."""
    logging.debug('Старт функции отправки сообщения с анимацией.')
    try:
        bot.send_animation(TELEGRAM_CHAT_ID, gif, caption=message)
        logging.info('Сообщение с анимацией отправлено')
    except telegram.error.TelegramError as error:
        logging.error(f'Анимация не была отправлено!!! Ошибка - {error}')
        send_message(bot, message)


def send_message_by_status(bot, status, message):
    """Выбор функции отправки сообщения в зависимости от статуса работы."""
    logging.debug('Старт функции проверки статуса работы.')
    homework_status = status[0].get('status')
    if homework_status == 'approved':
        comment = status[0].get("reviewer_comment")
        message = f'{message}\nКомментарий:\n{comment}'
        send_animation(bot, message, gif_ok)
    elif homework_status == 'rejected':
        comment = status[0].get("reviewer_comment")
        message = f'{message}\nКомментарий:\n{comment}'
        send_animation(bot, message, gif_fix)
    else:
        send_message(bot, message)


def get_api_answer(current_timestamp):
    """Делает запрос к API. Возвращает JSON ==> данные Python."""
    logging.debug('Старт функции запроса к API.')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Не успешный запрос к API! Ошибка - {error}'
        logging.error(message)
        raise ApiAnswerStatus(message)
    if response.status_code != HTTPStatus.OK:
        message = 'ENDPOINT неккоректен или недоступен!'
        logging.error(message)
        raise ApiAnswerStatus(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    logging.debug('Старт функции проверки корректности API.')
    if type(response) is not dict:
        logging.error(f'Тип response отличный от словаря - {type(response)}')
        raise TypeError
    if response == {}:
        logging.error('Пустой словарь в response')
        raise EmptyDictInResponse('Пустой словарь в response')
    if type(response.get('homeworks')) is not list:
        message = 'Ключ "homeworks" имеет тип данных отличный от list'
        logging.error(message)
        raise TypeError(message)
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    logging.debug('Старт функции проверки статуса работы.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        message = (
            f'Недокументированный статус работы - "{homework_status}"'
        )
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    logging.debug('Старт функции проверки переменных окружения.')
    check = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    if not check:
        logging.critical('Проверьте переменные окружения', exc_info=False)
    return check


def main():
    """Основная логика работы бота."""
    send_msg = set()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        sys.exit('Проблема с переменными окружения, завершение программы!')

    while True:
        try:
            current_timestamp = int(time.time()) - RETRY_TIME
            answer = get_api_answer(current_timestamp)
            homeworks = check_response(answer)
            if homeworks:
                status = parse_status(homeworks[0])
                send_message_by_status(bot, homeworks, status)
            else:
                logging.debug('Новый статус отсутствует.')
        except Exception as error:
            message = f'Сбой в работе программы!\n\n{error}'
            if message not in send_msg:
                send_message(bot, message)
                send_msg.add(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
