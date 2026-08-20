# -*- coding: utf-8 -*-
"""Сборка ZIP-архива проекта для передачи без GitHub.

    python advanced/make_archive.py [--out ПАПКА]

В архив попадает всё, что нужно для запуска: ноутбуки с исполненными
результатами, код подпроекта, синтетические данные, requirements и инструкция.
Не попадает: виртуальное окружение, история git, кэши, логи и чекпоинты —
их получатель создаёт у себя сам.
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Research_analysis_python'

EXCLUDE_DIRS = {'.venv', '.git', '__pycache__', '.ipynb_checkpoints',
                '.pytest_cache', 'node_modules'}
EXCLUDE_SUFFIX = {'.log', '.pyc', '.zip'}
EXCLUDE_NAMES = {'.DS_Store', 'Thumbs.db'}


def included(p: Path) -> bool:
    rel = p.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    return p.suffix not in EXCLUDE_SUFFIX and p.name not in EXCLUDE_NAMES


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT.parent),
                    help='куда положить архив (по умолчанию — рядом с папкой проекта)')
    args = ap.parse_args()

    out = Path(args.out).expanduser().resolve() / f'{NAME}.zip'
    out.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and included(p))
    if not files:
        raise SystemExit('Нечего архивировать')

    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            # внутри архива всё лежит в одной папке — распакуется аккуратно
            z.write(f, Path(NAME) / f.relative_to(ROOT))

    size_mb = out.stat().st_size / 1024 / 1024
    print(f'Архив: {out}')
    print(f'Файлов: {len(files)}, размер: {size_mb:.1f} МБ')
    print('\nСодержимое верхнего уровня:')
    for item in sorted({f.relative_to(ROOT).parts[0] for f in files}):
        print('  ', item)


if __name__ == '__main__':
    main()
