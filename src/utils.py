from bs4 import BeautifulSoup
from requests import RequestException

from exceptions import ParserFindTagException

MESSAGE_GET_RESPONSE_CONNECTION_ERROR_URL = (
    'Возникла ошибка при загрузке страницы {url}: {str(error)}'
)
FIND_TAG_ERROR_MESSAGE = 'Не найден тег {tag} {attrs}'


def get_response(session, url, encoding='utf-8'):
    """Перехват ошибки RequestException."""
    try:
        response = session.get(url)
        response.encoding = encoding
        return response
    except RequestException as error:
        raise ConnectionError(
            MESSAGE_GET_RESPONSE_CONNECTION_ERROR_URL.format(
                url=url, error=error
            )
        ) from error


def get_soup(session, url, features='lxml'):
    soup = BeautifulSoup(get_response(session, url).text, features=features)
    return soup


def find_tag(soup, tag, attrs=None):
    """Перехват ошибки поиска тегов."""
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_message = FIND_TAG_ERROR_MESSAGE.format(tag=tag, attrs=attrs)
        raise ParserFindTagException(error_message)
    return searched_tag
