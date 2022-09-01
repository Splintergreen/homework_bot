import os
import requests
import telegram
import logging
import time
from dotenv import load_dotenv
import sys
from http import HTTPStatus
from exeptions import ApiAnswerStatus, EmptyDictInResponse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

secret_token = os.getenv('TOKEN')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщения в Telegramm."""
    chat_id = TELEGRAM_CHAT_ID
    gif_ok = 'https://i.gifer.com/C6b.gif'
    gif_fix = 'https://partnerkin.com/storage/files/file_1573820864.gif'
    try:
        bot.send_message(chat_id, message)
        if 'понравилось' in message:
            try:
                bot.sendDocument(chat_id, document=gif_ok)
            except Exception:
                logging.info('Отсутствует Gif "успешная проверка"')
        elif 'замечания' in message:
            try:
                bot.sendDocument(chat_id, document=gif_fix)
            except Exception:
                logging.info('Отсутствует Gif "устранение замечаний"')
        logging.info('Сообщение отправлено')
    except Exception as error:
        logging.error(f'Сообщение не было отправлено!!! Ошибка - {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к API. Возвращает JSON ==> данные Python."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Не успешный запрос к API! Ошибка - {error}'
        logging.error(message)
        raise ApiAnswerStatus(message)
    if homework_statuses.status_code != HTTPStatus.OK:
        logging.error(message)
        message = 'Проверьте корректность ENDPOINT'
        raise ApiAnswerStatus(message)
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) is not dict:
        logging.error(f'Тип response отличный от словаря - {type(response)}')
        raise TypeError
    elif response == {}:
        logging.error('Пустой словарь в response')
        raise EmptyDictInResponse('Пустой словарь в response')
    elif type(response.get('homeworks')) is not list:
        message = 'Ключ "homeworks" имеет тип данных отличный от list'
        logging.error(message)
        raise TypeError(message)
    else:
        return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        message = (
            f'Недокументированный статус работы - "{homework_status}"'
        )
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    check = bool(PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)
    if not check:
        logging.critical('Проверьте переменные окружения', exc_info=False)
    return check


def main():
    """Основная логика работы бота."""
    send_msg = []
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        try:
            check_tokens()
            current_timestamp = int(time.time()) - RETRY_TIME
            answer = get_api_answer(current_timestamp)
            response = check_response(answer)
            status = parse_status(response[0])
            send_message(bot, status)
            time.sleep(RETRY_TIME)
        except IndexError:
            logging.debug('Новый статус отсутствует.')
            continue
        except Exception as error:
            message = f'Сбой в работе программы!\n\n{error}'
            if message not in send_msg:
                send_message(bot, message)
                send_msg.append(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
