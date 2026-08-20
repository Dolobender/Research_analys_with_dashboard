# -*- coding: utf-8 -*-
"""Обновление проекта

    python advanced/run_all.py            # данные + ноутбуки
    python advanced/run_all.py --no-data  # только ноутбуки

Шаги:
1. генерация синтетических данных (make_synthetic_data.py в корне);
2. валидация данных (src.data.assert_sane);
3. сборка ноутбуков подпроекта из build_notebooks.py;
4. исполнение всех ноутбуков, включая оригинальный;
5. проверка, что ни в одном не осталось ячеек с ошибкой.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable

NOTEBOOKS = [
    ROOT / 'Проект ИАД рынка еды.ipynb',
    HERE / '01_Статистическая_проверка.ipynb',
    HERE / '02_Скоринг_локаций.ipynb',
]


def step(msg: str) -> None:
    print(f'\n=== {msg} ' + '=' * max(0, 60 - len(msg)))


def run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        sys.exit(f'Шаг завершился с ошибкой: {" ".join(cmd)}')


def check(path: Path) -> int:
    nb = json.loads(path.read_text(encoding='utf-8'))
    errors = [o for c in nb['cells'] for o in c.get('outputs', [])
              if o.get('output_type') == 'error']
    images = sum(1 for c in nb['cells'] for o in c.get('outputs', [])
                 if any(k.startswith('image/') for k in (o.get('data') or {})))
    executed = sum(1 for c in nb['cells']
                   if c['cell_type'] == 'code' and c.get('execution_count'))
    status = 'OK' if not errors else f'ОШИБОК: {len(errors)}'
    print(f'  {path.name:<45} ячеек: {executed:>3}  графиков: {images:>3}  {status}')
    for e in errors[:3]:
        print(f'      {e["ename"]}: {e["evalue"][:120]}')
    return len(errors)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-data', action='store_true', help='не перегенерировать датасеты')
    args = ap.parse_args()

    if not args.no_data:
        step('1/4 Генерация синтетических данных')
        run([PY, 'make_synthetic_data.py'])

    step('2/4 Валидация данных')
    sys.path.insert(0, str(HERE))
    from src import data as D  # noqa: E402
    df = D.load()
    D.assert_sane(df)
    print(f'  {len(df):,} строк после очистки, проверки пройдены'.replace(',', ' '))

    step('3/4 Сборка ноутбуков подпроекта')
    run([PY, str(HERE / 'build_notebooks.py')])
    run([PY, str(HERE / 'add_bridge.py')])

    step('4/4 Исполнение ноутбуков')
    run([PY, '-m', 'nbconvert', '--to', 'notebook', '--execute', '--inplace',
         '--ExecutePreprocessor.timeout=1800'] + [str(p) for p in NOTEBOOKS])

    step('Проверка результата')
    total = sum(check(p) for p in NOTEBOOKS)
    if total:
        sys.exit(f'\nЕсть ячейки с ошибками: {total}')
    print('\nГотово. Дашборд: streamlit run advanced/app/dashboard.py')


if __name__ == '__main__':
    main()
