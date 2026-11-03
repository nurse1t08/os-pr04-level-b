#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f numbers.txt ]]; then python3 gen_numbers.py; fi
python3 benchmark.py --repeats 3
