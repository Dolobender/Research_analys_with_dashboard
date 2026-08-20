# -*- coding: utf-8 -*-
"""Проверка гипотез вместо утверждений «на глаз».

В оригинальном исследовании выводы вида «различия невелики, но статистически
значимы» сделаны без единого теста. Здесь каждая такая формулировка
подкреплена критерием, размером эффекта и доверительным интервалом.

Везде используются непараметрические критерии: распределения чека и числа
мест сильно скошены вправо, нормальность не выполняется.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

ALPHA = 0.05


# --------------------------------------------------------------------------
# вспомогательное
# --------------------------------------------------------------------------
def bootstrap_ci(x, func=np.median, n_boot=5000, ci=95, seed=42):
    """Бутстрэп-интервал для произвольной статистики."""
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    if len(x) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    boot = func(rng.choice(x, size=(n_boot, len(x)), replace=True), axis=1)
    lo, hi = (100 - ci) / 2, 100 - (100 - ci) / 2
    return float(np.percentile(boot, lo)), float(np.percentile(boot, hi))


def bootstrap_diff_ci(a, b, func=np.median, n_boot=5000, ci=95, seed=42):
    """Бутстрэп-интервал для разности статистик двух групп (a - b)."""
    a = np.asarray(pd.Series(a).dropna(), dtype=float)
    b = np.asarray(pd.Series(b).dropna(), dtype=float)
    if len(a) < 2 or len(b) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    da = func(rng.choice(a, size=(n_boot, len(a)), replace=True), axis=1)
    db = func(rng.choice(b, size=(n_boot, len(b)), replace=True), axis=1)
    diff = da - db
    lo, hi = (100 - ci) / 2, 100 - (100 - ci) / 2
    return float(np.percentile(diff, lo)), float(np.percentile(diff, hi))


def rank_biserial(a, b) -> float:
    """Размер эффекта для критерия Манна—Уитни.

    Интерпретация: вероятность того, что случайный объект из группы a больше
    случайного объекта из b, приведённая к шкале [-1, 1]. |r| < 0.1 — эффект
    пренебрежимо мал, 0.1–0.3 — малый, 0.3–0.5 — средний, > 0.5 — большой.
    """
    a = pd.Series(a).dropna()
    b = pd.Series(b).dropna()
    if a.empty or b.empty:
        return np.nan
    u = stats.mannwhitneyu(a, b, alternative='two-sided').statistic
    return float(2 * u / (len(a) * len(b)) - 1)


def epsilon_squared(groups) -> float:
    """Размер эффекта для критерия Краскела—Уоллиса (доля объяснённой дисперсии рангов)."""
    groups = [pd.Series(g).dropna() for g in groups]
    groups = [g for g in groups if len(g) > 0]
    n = sum(len(g) for g in groups)
    if n <= len(groups):
        return np.nan
    h = stats.kruskal(*groups).statistic
    return float((h - len(groups) + 1) / (n - len(groups)))


def cramers_v(table: pd.DataFrame) -> float:
    """Размер эффекта для критерия хи-квадрат на таблице сопряжённости."""
    chi2 = stats.chi2_contingency(table).statistic
    n = table.values.sum()
    return float(np.sqrt(chi2 / (n * (min(table.shape) - 1))))


def verdict(p: float, alpha: float = ALPHA) -> str:
    return 'H0 отвергается' if p < alpha else 'H0 не отвергается'


def effect_label(r: float) -> str:
    r = abs(r)
    if np.isnan(r):
        return '—'
    if r < 0.1:
        return 'пренебрежимо мал'
    if r < 0.3:
        return 'малый'
    if r < 0.5:
        return 'средний'
    return 'большой'


# --------------------------------------------------------------------------
# гипотезы
# --------------------------------------------------------------------------
def test_center_vs_rest(df: pd.DataFrame, col: str = 'middle_avg_bill') -> dict:
    """H0: распределение `col` в ЦАО не отличается от остальных округов."""
    a = df.loc[df['is_center'], col].dropna()
    b = df.loc[~df['is_center'], col].dropna()
    res = stats.mannwhitneyu(a, b, alternative='two-sided')
    r = rank_biserial(a, b)
    lo, hi = bootstrap_diff_ci(a, b)
    return {
        'гипотеза': f'{col}: ЦАО vs остальные округа',
        'критерий': 'Манна—Уитни (двусторонний)',
        'n ЦАО': len(a), 'n остальные': len(b),
        'медиана ЦАО': round(float(a.median()), 1),
        'медиана остальные': round(float(b.median()), 1),
        'разность медиан': round(float(a.median() - b.median()), 1),
        '95% ДИ разности': (round(lo, 1), round(hi, 1)),
        'p-value': float(res.pvalue),
        'размер эффекта (r)': round(r, 3),
        'сила эффекта': effect_label(r),
        'вывод': verdict(res.pvalue),
    }


def test_rating_by_category(df: pd.DataFrame) -> dict:
    """H0: медианный рейтинг одинаков во всех категориях заведений."""
    groups = [g['rating'].dropna() for _, g in df.groupby('category')]
    res = stats.kruskal(*groups)
    eps = epsilon_squared(groups)
    return {
        'гипотеза': 'рейтинг одинаков во всех категориях',
        'критерий': 'Краскела—Уоллиса',
        'k групп': len(groups), 'n': int(sum(len(g) for g in groups)),
        'H': round(float(res.statistic), 2),
        'p-value': float(res.pvalue),
        'размер эффекта (eps^2)': round(eps, 4),
        'сила эффекта': effect_label(np.sqrt(max(eps, 0))),
        'вывод': verdict(res.pvalue),
    }


def pairwise_rating(df: pd.DataFrame, alpha: float = ALPHA) -> pd.DataFrame:
    """Попарные сравнения рейтинга категорий с поправкой Холма на множественность."""
    cats = sorted(df['category'].dropna().unique())
    rows = []
    for i, c1 in enumerate(cats):
        for c2 in cats[i + 1:]:
            a = df.loc[df['category'] == c1, 'rating'].dropna()
            b = df.loc[df['category'] == c2, 'rating'].dropna()
            p = stats.mannwhitneyu(a, b, alternative='two-sided').pvalue
            r = rank_biserial(a, b)
            rows.append({'категория A': c1, 'категория B': c2,
                         'медиана A': round(float(a.median()), 2),
                         'медиана B': round(float(b.median()), 2),
                         'p-value': float(p), 'r': round(r, 3),
                         'сила эффекта': effect_label(r)})
    out = pd.DataFrame(rows).sort_values('p-value').reset_index(drop=True)
    # поправка Холма: p_(i) * (m - i), с накопительным максимумом
    m = len(out)
    out['p_holm'] = np.maximum.accumulate(
        np.minimum(out['p-value'].values * (m - np.arange(m)), 1.0))
    out['значимо'] = out['p_holm'] < alpha
    return out


def test_chain_vs_category(df: pd.DataFrame) -> dict:
    """H0: сетевость не связана с категорией заведения."""
    table = pd.crosstab(df['category'], df['chain'])
    res = stats.chi2_contingency(table)
    v = cramers_v(table)
    return {
        'гипотеза': 'сетевость не зависит от категории',
        'критерий': 'хи-квадрат Пирсона',
        'chi2': round(float(res.statistic), 1),
        'df': int(res.dof),
        'p-value': float(res.pvalue),
        'размер эффекта (V Крамера)': round(v, 3),
        'сила эффекта': effect_label(v),
        'вывод': verdict(res.pvalue),
    }


def test_rating_vs_bill(df: pd.DataFrame) -> dict:
    """H0: рейтинг не связан со средним чеком (монотонной связи нет)."""
    sub = df[['rating', 'middle_avg_bill']].dropna()
    rho, p = stats.spearmanr(sub['rating'], sub['middle_avg_bill'])
    return {
        'гипотеза': 'рейтинг не связан со средним чеком',
        'критерий': 'ранговая корреляция Спирмена',
        'n': len(sub),
        'rho': round(float(rho), 3),
        'p-value': float(p),
        'сила эффекта': effect_label(rho),
        'вывод': verdict(p),
    }


def summary(df: pd.DataFrame) -> pd.DataFrame:
    """Сводная таблица по всем гипотезам — то, что стоит вынести в README."""
    tests = [test_center_vs_rest(df), test_rating_by_category(df),
             test_chain_vs_category(df), test_rating_vs_bill(df)]
    rows = [{'гипотеза (H0)': t['гипотеза'], 'критерий': t['критерий'],
             'p-value': f"{t['p-value']:.2e}", 'сила эффекта': t['сила эффекта'],
             'вывод': t['вывод']} for t in tests]
    return pd.DataFrame(rows)
