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
        if 'понравилось' in message:
            try:
                bot.send_animation(TELEGRAM_CHAT_ID, gif_ok, caption=message)
            except Exception:
                logging.info('Отсутствует Gif "успешная проверка"')
                bot.send_message(TELEGRAM_CHAT_ID, message)
        elif 'замечания' in message:
            try:
                bot.send_animation(TELEGRAM_CHAT_ID, gif_fix, caption=message)
            except Exception:
                logging.info('Отсутствует Gif "устранение замечаний"')
                bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение отправлено')
    except telegram.error.TelegramError as error:
        logging.error(f'Сообщение не было отправлено!!! Ошибка - {error}')


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
        logging.error(message)
        message = 'Проверьте корректность ENDPOINT'
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
    send_msg = set()  # Множество наполняется отправленными ошибками
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        try:
            check_tokens()
            current_timestamp = int(time.time()) - RETRY_TIME
            answer = get_api_answer(current_timestamp)
            homeworks = check_response(answer)
            status = parse_status(homeworks[0])
            send_message(bot, status)
        except IndexError:
            logging.debug('Новый статус отсутствует.')
            continue
        except Exception as error:
            message = f'Сбой в работе программы!\n\n{error}'
            if message not in send_msg:  # Была такая ошибка отправлена или нет
                send_message(bot, message)
                send_msg.add(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
