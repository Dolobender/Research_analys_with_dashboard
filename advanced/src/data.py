# -*- coding: utf-8 -*-
"""Единый слой загрузки и подготовки данных для подпроекта `advanced`.

Оригинальный ноутбук делает предобработку внутри себя. Здесь та же логика
вынесена в функции, чтобы ноутбуки подпроекта и Streamlit-дашборд работали
с одним и тем же датафреймом и не расходились в цифрах.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# корень репозитория: advanced/src/data.py -> advanced -> <репозиторий>
ROOT = Path(__file__).resolve().parents[2]

# Два источника. `datasets/` заполняет make_synthetic_data.py — цифры там
# выдуманные. Настоящие CSV Практикума кладутся в `datasets_real/` и в
# репозиторий не попадают; как только они появятся, интерфейс сам предложит
# переключиться. Разделение нужно, чтобы синтетику невозможно было принять
# за реальные данные.
SYNTHETIC_DIR = ROOT / 'datasets'
REAL_DIR = ROOT / 'datasets_real'
DATA_DIR = SYNTHETIC_DIR  # источник по умолчанию

FILES = ('rest_info.csv', 'rest_price.csv')

CENTER = 'Центральный административный округ'

# порядковая шкала ценовых категорий — нужна для корреляций и скоринга
PRICE_ORDER = ['низкие', 'ниже среднего', 'средние', 'выше среднего', 'высокие']
PRICE_RANK = {name: i for i, name in enumerate(PRICE_ORDER)}


def load_raw(data_dir: Path | str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Читает два исходных CSV как есть."""
    d = Path(data_dir) if data_dir else DATA_DIR
    info = pd.read_csv(d / 'rest_info.csv')
    price = pd.read_csv(d / 'rest_price.csv')
    return info, price


def clean(info: pd.DataFrame, price: pd.DataFrame) -> pd.DataFrame:
    """Объединяет, чистит и обогащает — повторяет шаги оригинального ноутбука."""
    df = info.merge(price, on='id', how='left')

    for col in ('rating', 'seats', 'middle_avg_bill', 'middle_coffee_cup'):
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['name_norm'] = df['name'].str.lower().str.strip()
    df['address_norm'] = df['address'].str.lower().str.strip()
    df = df.drop_duplicates(subset=['name_norm', 'address_norm'], keep='first')

    hours = df['hours'].astype(str)
    df['is_24_7'] = (hours.str.contains('ежедневно', case=False, na=False)
                     & hours.str.contains('круглосуточно|24', case=False, na=False))

    df['is_center'] = df['district'] == CENTER
    df['chain_type'] = df['chain'].map({1: 'Сетевые', 0: 'Несетевые'})
    df['price_rank'] = df['price'].map(PRICE_RANK)
    # короткое имя округа для подписей на графиках: «Юго-Западный АО»
    df['district_short'] = (df['district']
                            .str.replace(' административный округ', ' АО', regex=False))
    # аббревиатура для узких мест интерфейса: «ЮЗАО»
    df['district_abbr'] = df['district'].map(district_abbr)

    return df.reset_index(drop=True)


def district_abbr(name: str) -> str:
    """«Юго-Западный административный округ» -> «ЮЗАО»."""
    head = name.split(' административный')[0]
    letters = ''.join(part[0] for part in head.replace('-', ' ').split())
    return letters.upper() + 'АО'


def has_real() -> bool:
    """Есть ли настоящие датасеты в `datasets_real/`."""
    return all((REAL_DIR / f).exists() for f in FILES)


def has_synthetic() -> bool:
    """Сгенерированы ли синтетические датасеты в `datasets/`."""
    return all((SYNTHETIC_DIR / f).exists() for f in FILES)


def resolve_dir(synthetic: bool = True) -> Path:
    """Каталог данных под выбранный режим, с понятной ошибкой, если его нет."""
    if synthetic:
        if not has_synthetic():
            raise FileNotFoundError(
                f'Нет синтетических данных в {SYNTHETIC_DIR}. '
                'Выполните: python make_synthetic_data.py')
        return SYNTHETIC_DIR
    if not has_real():
        raise FileNotFoundError(
            f'Нет настоящих данных в {REAL_DIR}. Положите туда '
            f'{" и ".join(FILES)} — файлы Практикума в репозиторий не входят.')
    return REAL_DIR


def load(data_dir: Path | str | None = None, synthetic: bool = True) -> pd.DataFrame:
    """Загрузка + очистка одним вызовом. Основная точка входа.

    По умолчанию читает синтетические данные. `synthetic=False` переключает
    на `datasets_real/`; явный аргумент `data_dir` перекрывает оба режима.
    """
    return clean(*load_raw(data_dir or resolve_dir(synthetic)))


def quality_report(df: pd.DataFrame) -> pd.DataFrame:
    """Сводка по заполненности и типам — минимальная валидация данных."""
    rep = pd.DataFrame({
        'тип': df.dtypes.astype(str),
        'заполнено': df.notna().sum(),
        'пропусков': df.isna().sum(),
    })
    rep['пропусков, %'] = (rep['пропусков'] / len(df) * 100).round(1)
    rep['уникальных'] = df.nunique()
    return rep


def assert_sane(df: pd.DataFrame) -> None:
    """Проверки, которые должны выполняться на любом валидном срезе данных."""
    problems = []
    if df['id'].duplicated().any():
        problems.append('дубликаты id')
    if not df['rating'].dropna().between(0, 5).all():
        problems.append('рейтинг вне диапазона 0–5')
    if (df['seats'].dropna() < 0).any():
        problems.append('отрицательное число мест')
    if (df['middle_avg_bill'].dropna() <= 0).any():
        problems.append('неположительный средний чек')
    unknown = set(df['price'].dropna().unique()) - set(PRICE_ORDER)
    if unknown:
        problems.append(f'неизвестные ценовые категории: {sorted(unknown)}')
    if problems:
        raise AssertionError('Данные не прошли валидацию: ' + '; '.join(problems))


__all__ = ['ROOT', 'DATA_DIR', 'SYNTHETIC_DIR', 'REAL_DIR', 'FILES', 'CENTER',
           'PRICE_ORDER', 'PRICE_RANK', 'load_raw', 'clean', 'load',
           'has_real', 'has_synthetic', 'resolve_dir', 'quality_report',
           'assert_sane', 'district_abbr', 'np']
