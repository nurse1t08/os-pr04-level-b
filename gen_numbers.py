#!/usr/bin/env python3
"""Генератор 10 миллионов целых чисел, без случайных внешних файлов."""
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--count', type=int, default=10_000_000)
parser.add_argument('--output', type=Path, default=Path('numbers.txt'))
args = parser.parse_args()
if args.count < 1:
    parser.error('--count >= 1')
with args.output.open('w') as f:
    for n in range(args.count):
        f.write(f'{n % 1000}\n')
print(f'Записано {args.count} чисел в {args.output}')
