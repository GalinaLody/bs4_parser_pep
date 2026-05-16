import logging
import re
from collections import Counter
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL, MAIN_PEP_URL
from outputs import control_output
from utils import find_tag, get_response


def whats_new(session):
    """Собирает ссылки на статьи о нововведениях в Python,
    переходит по ним и забирает информацию об авторах и редакторах статей.
    """
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, features='lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (h1.text, dl_text)
        )
    return results


def latest_versions(session):
    """Собирает информацию о статусах версий Python."""
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
        else:
            raise Exception('Ничего не нашлось')
    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )
    return results


def download(session):
    """Скачивает архив с актуальной докуиентацией Python."""
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    docs_text_tag = find_tag(
        table_tag, 'a', {'href': re.compile(r'.+docs-text\.zip$')}
    )
    docs_text_link = docs_text_tag['href']
    archive_url = urljoin(downloads_url, docs_text_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    """собирает информацию о статусах документов PEP и их количестве."""
    response = get_response(session, MAIN_PEP_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    index_by_category = find_tag(
        soup, 'section', attrs={'id': 'index-by-category'}
    )
    tables_pep = index_by_category.find_all('tbody')
    all_statuses = []
    not_matching_status = []
    for table in tqdm(tables_pep):
        rows = table.find_all('tr')
        for row in rows[:5]:
            first_column_tag = find_tag(row, 'td')
            preview_status = first_column_tag.text[1:]
            second_column_tag = find_tag(row, 'a')
            href = second_column_tag['href']
            link_pep = urljoin(MAIN_PEP_URL, href)
            response = get_response(session, link_pep)
            if response is None:
                return
            soup = BeautifulSoup(response.text, features='lxml')
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
            all_statuses.append(real_status)
    if not_matching_status:
        message = '\n'.join(not_matching_status)
        logging.info(
            f'Несовпадающие статусы: {message}'
        )
    results = [('Статус', 'Количество')]
    counter = Counter(all_statuses)
    total_count_pep = 0
    for status, count in counter.items():
        results.append((status, count))
        total_count_pep += count
    results.append(('Total', total_count_pep))
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')
    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()
    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
