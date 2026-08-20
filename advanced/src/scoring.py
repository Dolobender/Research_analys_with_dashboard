# -*- coding: utf-8 -*-
"""Скоринг связок «округ × категория»: где открывать заведение.

Оригинальное исследование останавливается на описании рынка. Здесь описание
превращается в ранжированный список решений: каждая пара (округ, категория)
получает оценку привлекательности от 0 до 100 по пяти факторам.

Факторы (все приводятся к шкале 0–1 через min-max по всем парам):

1. `competition`   — насыщенность ниши: сколько заведений этой категории уже
                     работает в округе. Меньше — лучше (инвертируется).
2. `revenue`       — медианный средний чек в паре. Больше — лучше.
3. `quality_gap`   — слабость действующих игроков: 5 − средний рейтинг.
                     Больше — лучше (легче выделиться качеством).
4. `fragmentation` — доля несетевых заведений. Больше — лучше: рынок не занят
                     сетями с их бюджетами и узнаваемостью.
5. `traffic`       — размер рынка округа целиком (все заведения). Больше —
                     лучше как прокси платёжеспособного трафика.

Веса задаются пользователем (в дашборде — слайдерами) и нормируются к сумме 1,
поэтому итог всегда в диапазоне 0–100 и сравним между конфигурациями.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FACTORS = ['competition', 'revenue', 'quality_gap', 'fragmentation', 'traffic']

FACTOR_LABELS = {
    'competition': 'Свободность ниши',
    'revenue': 'Потенциал выручки',
    'quality_gap': 'Слабость конкурентов',
    'fragmentation': 'Фрагментированность',
    'traffic': 'Размер рынка округа',
}

DEFAULT_WEIGHTS = {
    'competition': 0.30,
    'revenue': 0.25,
    'quality_gap': 0.15,
    'fragmentation': 0.15,
    'traffic': 0.15,
}

MIN_OBJECTS = 30  # пары с меньшим числом наблюдений статистически ненадёжны


def _minmax(s: pd.Series) -> pd.Series:
    """Min-max нормализация; константный столбец превращается в 0.5."""
    lo, hi = s.min(), s.max()
    if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


def build_matrix(df: pd.DataFrame, min_objects: int = MIN_OBJECTS) -> pd.DataFrame:
    """Собирает сырые метрики по каждой паре (округ, категория)."""
    district_size = df.groupby('district')['id'].count().rename('district_total')

    g = df.groupby(['district', 'category'])
    m = pd.DataFrame({
        'n': g['id'].count(),
        'median_bill': g['middle_avg_bill'].median(),
        'mean_rating': g['rating'].mean(),
        'chain_share': g['chain'].mean(),
        'median_seats': g['seats'].median(),
    }).reset_index()

    m = m.merge(district_size, on='district', how='left')
    m = m[m['n'] >= min_objects].copy()
    # пары без данных о чеке скорить нечем — чек несёт четверть веса
    m = m[m['median_bill'].notna()].copy()
    return m.reset_index(drop=True)


def score(df: pd.DataFrame, weights: dict | None = None,
          min_objects: int = MIN_OBJECTS) -> pd.DataFrame:
    """Возвращает пары (округ, категория), отсортированные по убыванию оценки."""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: v for k, v in weights.items() if k in FACTORS})
    total = sum(w.values())
    if total <= 0:
        raise ValueError('Сумма весов должна быть положительной')
    w = {k: v / total for k, v in w.items()}

    m = build_matrix(df, min_objects=min_objects)
    if m.empty:
        return m

    m['competition'] = 1 - _minmax(m['n'])
    m['revenue'] = _minmax(m['median_bill'])
    m['quality_gap'] = _minmax(5 - m['mean_rating'])
    m['fragmentation'] = _minmax(1 - m['chain_share'])
    m['traffic'] = _minmax(m['district_total'])

    m['score'] = sum(m[f] * w[f] for f in FACTORS) * 100
    m['score'] = m['score'].round(1)
    m['rank'] = m['score'].rank(ascending=False, method='min').astype(int)

    return m.sort_values('score', ascending=False).reset_index(drop=True)


def explain(row: pd.Series, weights: dict | None = None) -> pd.DataFrame:
    """Раскладывает оценку одной пары на вклады факторов."""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: v for k, v in weights.items() if k in FACTORS})
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}
    return pd.DataFrame({
        'фактор': [FACTOR_LABELS[f] for f in FACTORS],
        'значение (0–1)': [round(float(row[f]), 3) for f in FACTORS],
        'вес': [round(w[f], 3) for f in FACTORS],
        'вклад в оценку': [round(float(row[f]) * w[f] * 100, 1) for f in FACTORS],
    }).sort_values('вклад в оценку', ascending=False).reset_index(drop=True)


def readable(m: pd.DataFrame, top: int | None = 15) -> pd.DataFrame:
    """Человекочитаемая витрина результата — для README и презентации."""
    out = m.copy()
    if top:
        out = out.head(top)
    out = pd.DataFrame({
        'Ранг': out['rank'],
        'Округ': out['district'].str.replace(' административный округ', ' АО', regex=False),
        'Категория': out['category'],
        'Оценка': out['score'],
        'Заведений': out['n'],
        'Медианный чек, ₽': out['median_bill'].round(0),
        'Средний рейтинг': out['mean_rating'].round(2),
        'Доля сетей, %': (out['chain_share'] * 100).round(1),
    })
    return out.reset_index(drop=True)
