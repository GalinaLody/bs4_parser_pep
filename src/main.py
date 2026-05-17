import logging
import re
from collections import defaultdict
from urllib.parse import urljoin

import requests_cache
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL, MAIN_PEP_URL
from outputs import control_output
from utils import find_tag, get_soup

# Добрый день!
# После того как студентов перевели из Пачки в новый Месенджер
# у студентов(и меня) болше нет возможности обращатся к ревьюеру напрямую.
# Нет физической возможностии отправить сообщение в Мессенджере.
# Все обсуждения замечаний ревьюера возможны только с наставником
# в одном чате Мессенджераю.
# По этой причине я оставила 3 комментария, почему я не внесла изменения
# (не исправила замечания) в коде. 

MESSAGE_RAISE_LATEST_VERSIONS = 'Ничего не нашлось'
MESSAGE_DOWNLOAD_FILE = 'Архив был загружен и сохранён: {archive_path}'
MESSAGE_PEP_NOT_MATCHING_STATUS = 'Несовпадающие статусы: {message}'
MESSAGE_MAIN_START = 'Парсер запущен!'
MESSAGE_MAIN_ARG_COMMAND = 'Аргументы командной строки: {args}'
MESSAGE_MAIN_END = 'Парсер завершил работу.'
MESSAGE_MAIN_EXCEPTION = 'Возникла ошибка'
MESSAGE_CONNECTION_ERROR_URL = (
    'Возникла ошибка при загрузке страницы {url}'
)


def whats_new(session):
    """Собирает ссылки на статьи о нововведениях в Python,
    переходит по ним и забирает информацию об авторах и редакторах статей.
    """
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    soup = get_soup(session, whats_new_url)
    sections_by_python = soup.select(
        '#what-s-new-in-python div.toctree-wrapper li.toctree-l1'
    )
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        soup = get_soup(session, version_link)
        if soup is None:
            logging.warning(
                MESSAGE_CONNECTION_ERROR_URL.format(url=version_link)
            )
            continue
        results.append(
            (
                find_tag(soup, 'h1').text,
                find_tag(soup, 'dl').text.replace('\n', ' ')
            )
        )
    return results


def latest_versions(session):
    """Собирает информацию о статусах версий Python."""
    soup = get_soup(session, MAIN_DOC_URL)
    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        # В переменной ul_tags хранятся два списка с тегами <ul>,
        # но парсеру нужен только первый.
        # Его можно найти по тексту, который содержится в строках списка,
        # например, по фразе All versions — это делается через цикл.
        # Циклу задаётся условие: если в списке есть фраза All versions,
        # то нужно найти в нём все теги <a>, а если нет
        # — вывести сообщение «Ничего не нашлось».
        # Эта часть кода написана Яндекс.Практикум, а не мной.
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
        else:
            raise ValueError(MESSAGE_RAISE_LATEST_VERSIONS)
    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (a_tag['href'], version, status)
        )
    return results


def download(session):
    """Скачивает архив с актуальной докуиентацией Python."""
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    soup = get_soup(session, downloads_url)
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    docs_text_link = main_tag.select_one(
        'table.docutils a[href$="docs-text.zip"]'
    )['href']
    archive_url = urljoin(downloads_url, docs_text_link)
    filename = archive_url.split('/')[-1]
    # не могу убрать эту папку в константы.
    # этот код фактически подготовлен Яндекс.практикум и тесты требуют
    # чтобы эта папка вычислялась именно в функции.
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(MESSAGE_DOWNLOAD_FILE.format(archive_path=archive_path))


def pep(session):
    """Cобирает информацию о статусах документов PEP и их количестве."""
    soup = get_soup(session, MAIN_PEP_URL)
    index_by_category = find_tag(
        soup, 'section', attrs={'id': 'index-by-category'}
    )
    tables_pep = index_by_category.find_all('tbody')
    status_counter = defaultdict(int)
    not_matching_status = []
    for table in tqdm(tables_pep):
        rows = table.find_all('tr')
        for row in rows[:5]:
            first_column_tag = find_tag(row, 'td')
            preview_status = first_column_tag.text[1:]
            second_column_tag = find_tag(row, 'a')
            href = second_column_tag['href']
            link_pep = urljoin(MAIN_PEP_URL, href)
            soup = get_soup(session, link_pep)
            if soup is None:
                logging.warning(
                    MESSAGE_CONNECTION_ERROR_URL.format(url=link_pep)
                )
                continue
            all_dt_tags = soup.find_all('dt')
            for dt in all_dt_tags:
                if 'Status' in dt.get_text():
                    dt_status_teg = dt
                    break
            tag_status = dt_status_teg.find_next_sibling('dd')
            real_status = tag_status.string
            if real_status not in EXPECTED_STATUS[preview_status]:
                string = (
                    f'{link_pep}\n Статус в карточке: {real_status}\n'
                    f'Ожидаемые статусы:{EXPECTED_STATUS[preview_status]}'
                )
                not_matching_status.append(string)
            status_counter[real_status] += 1
    if not_matching_status:
        message = '\n'.join(not_matching_status)
        logging.info(
            MESSAGE_PEP_NOT_MATCHING_STATUS.format(message=message)
        )
    return [
        ('Статус', 'Количество'),
        *status_counter.items(),
        ('Всего', sum(status_counter.values()))
    ]


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    try:
        configure_logging()
        logging.info(MESSAGE_MAIN_START)
        arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
        args = arg_parser.parse_args()
        logging.info(MESSAGE_MAIN_ARG_COMMAND.format(args=args))
        session = requests_cache.CachedSession()
        if args.clear_cache:
            session.cache.clear()
        parser_mode = args.mode
        results = MODE_TO_FUNCTION[parser_mode](session)
        if results is not None:
            control_output(results, args)
        logging.info(MESSAGE_MAIN_END)
    except Exception:
        logging.exception(MESSAGE_MAIN_EXCEPTION, stack_info=True)


if __name__ == '__main__':
    main()
