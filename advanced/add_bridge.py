# -*- coding: utf-8 -*-
"""Вставляет в оригинальный ноутбук ссылки-переходы в подпроект `advanced`.

Идемпотентно: повторный запуск не плодит дубликаты. Сам анализ не трогает —
добавляются только markdown-ячейки в начало и конец.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / 'Проект ИАД рынка еды.ipynb'

MARK = '<!-- advanced-bridge -->'

TOP = f'''{MARK}
> ### Есть продолжение: подпроект [`advanced/`](advanced/README.md)
>
> Этот ноутбук описывает рынок. Подпроект `advanced` идёт дальше:
>
> | | |
> |---|---|
> | [01 · Статистическая проверка](advanced/01_Статистическая_проверка.ipynb) | выводы ниже проверены критериями, с размерами эффекта и доверительными интервалами |
> | [02 · Скоринг локаций](advanced/02_Скоринг_локаций.ipynb) | рекомендации превращены в ранжированную оценку пар «округ × категория» |
> | Дашборд | `streamlit run advanced/app/dashboard.py` — те же данные в интерактиве |
>
> Подпроект читает те же данные и ничего здесь не меняет.
'''

BOTTOM = f'''{MARK}
---

### Что дальше

Выводы выше сформулированы описательно. Насколько они устойчивы и что из них
следует практически — в подпроекте [`advanced/`](advanced/README.md):

- [**01 · Статистическая проверка**](advanced/01_Статистическая_проверка.ipynb) —
  критерии Манна—Уитни, Краскела—Уоллиса, хи-квадрат и Спирмена вместо
  утверждений на глаз; размеры эффекта показывают, где значимость реальна,
  а где она куплена размером выборки.
- [**02 · Скоринг локаций**](advanced/02_Скоринг_локаций.ipynb) —
  оценка привлекательности каждой пары «округ × категория» с проверкой
  на чувствительность к весам.
- **Интерактивный дашборд** — `streamlit run advanced/app/dashboard.py`
'''


def cell(text: str, cid: str) -> dict:
    return {'cell_type': 'markdown', 'id': cid, 'metadata': {},
            'source': text.strip('\n').splitlines(keepends=True)}


def main() -> None:
    nb = json.loads(NB.read_text(encoding='utf-8'))
    cells = [c for c in nb['cells']
             if not (c['cell_type'] == 'markdown' and MARK in ''.join(c['source']))]

    # ячейка-заголовок остаётся первой, переход — сразу под ней
    cells.insert(1, cell(TOP, 'advanced-bridge-top'))
    cells.append(cell(BOTTOM, 'advanced-bridge-bottom'))

    nb['cells'] = cells
    NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Ссылки на подпроект вставлены: {NB.name} ({len(cells)} ячеек)')


if __name__ == '__main__':
    main()
