#!/usr/bin/env python3
"""CPU: 1 поток/4 потока/4 процесса; I/O: 20 HTTP запросов 3 способами."""
import argparse
import csv
import multiprocessing as mp
import os
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

NUMBERS = []  # fork-потомки наследуют список через COW


def sum_range(bounds):
    start, end = bounds
    total = 0
    for i in range(start, end):
        total += NUMBERS[i]  # намеренно Python-цикл: чисто CPU-bound
    return total


def chunks(n, jobs=4):
    return [(n * i // jobs, n * (i + 1) // jobs) for i in range(jobs)]


def cpu_sequential():
    return sum_range((0, len(NUMBERS)))


def cpu_threaded():
    with ThreadPoolExecutor(max_workers=4) as pool:
        return sum(pool.map(sum_range, chunks(len(NUMBERS))))


def cpu_processed():
    # Для Ubuntu используем fork, иначе 10 млн чисел пришлось бы передавать в пул заново.
    if 'fork' not in mp.get_all_start_methods():
        raise RuntimeError('Для CPU-теста необходим Linux/macOS с fork')
    with ProcessPoolExecutor(max_workers=4, mp_context=mp.get_context('fork')) as pool:
        return sum(pool.map(sum_range, chunks(len(NUMBERS))))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(0.08)  # одинаковая учебная сетевая задержка
        body = f'response from {self.path}\n'.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def download(url):
    with urlopen(url, timeout=5) as response:
        return len(response.read())


def io_sequential(urls):
    return list(map(download, urls))


def io_threaded(urls):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(download, urls))


def io_processed(urls):
    # spawn безопаснее, так как локальный HTTP-сервер уже запущен в потоке.
    with ProcessPoolExecutor(max_workers=4, mp_context=mp.get_context('spawn')) as pool:
        return list(pool.map(download, urls))


def demo_memory():
    shared = [1]
    def thread_change():
        shared[0] = 2
    t = threading.Thread(target=thread_change)
    t.start(); t.join()
    print('После потока global list:', shared)
    def process_change():
        shared[0] = 3
        print('В дочернем процессе global list:', shared, flush=True)
    p = mp.get_context('fork').Process(target=process_change)
    p.start(); p.join()
    print('После процесса global list в родителе:', shared)
    assert shared == [2]


def benchmark(label, fn, repeats, expected, rows):
    durations = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        durations.append(time.perf_counter() - start)
        assert result == expected, f'{label}: неверный результат'
    med = statistics.median(durations)
    rows.append((label, round(med, 5), repeats))
    print(f'{label:<30} {med:.4f} с (медиана {repeats} прогонов)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', default='numbers.txt')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats >= 1')
    global NUMBERS
    NUMBERS = [int(x) for x in Path(args.file).read_text().splitlines()]
    expected = sum(NUMBERS)
    print(f'Чисел: {len(NUMBERS)}; ядер CPU: {os.cpu_count()}; контрольная сумма: {expected}')
    print('Время чтения файла НЕ включено в измерение.\n')
    rows = []
    for label, fn in [('CPU 1 поток', cpu_sequential),
                      ('CPU 4 потока', cpu_threaded),
                      ('CPU 4 процесса', cpu_processed)]:
        benchmark(label, fn, args.repeats, expected, rows)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        urls = [f'http://127.0.0.1:{server.server_port}/file-{i}' for i in range(20)]
        expected_lengths = io_sequential(urls)
        print('\nСеть: 20 запросов к локальному серверу (задержка 80 мс/запрос).')
        for label, fn in [('I/O последовательно', io_sequential),
                          ('I/O 4 потока', io_threaded),
                          ('I/O 4 процесса', io_processed)]:
            benchmark(label, lambda f=fn: f(urls), args.repeats, expected_lengths, rows)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    print('\nПамять:')
    demo_memory()
    with open('results.csv', 'w', newline='') as f:
        csv.writer(f).writerows([['method', 'median_seconds', 'repeats'], *rows])
    print('\nТаблица сохранена в results.csv')


if __name__ == '__main__':
    main()
