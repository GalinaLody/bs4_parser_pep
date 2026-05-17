import csv
import datetime as dt
import logging

from prettytable import PrettyTable

from constants import (BASE_DIR, DATETIME_FORMAT,
                       OUTPUT_FILE, OUTPUT_PRETTY,
                       RESULTS_DIR)

MESSAGE_FILE_OUTPUT_SAVE_FILE = 'Файл с результатами был сохранён: {file_path}'


def default_output(results, *args):
    """Вывод данных по умолчанию."""
    for row in results:
        print(*row)


def pretty_output(results, *args):
    """Вывод данных в формате таблицы."""
    table = PrettyTable()
    table.field_names = results[0]
    table.align = 'l'
    table.add_rows(results[1:])
    print(table)


def file_output(results, cli_args):
    """Сохранение данных в файле в формате csv."""
    results_dir = BASE_DIR / RESULTS_DIR
    results_dir.mkdir(exist_ok=True)
    parser_mode = cli_args.mode
    now_formatted = dt.datetime.now().strftime(DATETIME_FORMAT)
    file_name = f'{parser_mode}_{now_formatted}.csv'
    file_path = results_dir / file_name
    with open(file_path, 'w', encoding='utf-8') as f:
        csv.writer(f, dialect=csv.unix_dialect).writerows(results)
    logging.info(MESSAGE_FILE_OUTPUT_SAVE_FILE.format(file_path=file_path))


CONTROL_OUTPUT = {
    OUTPUT_FILE: file_output,
    OUTPUT_PRETTY: pretty_output,
    None: default_output

}


def control_output(results, cli_args):
    """Контролирует вывод данных."""
    CONTROL_OUTPUT[cli_args.output](results, cli_args)
