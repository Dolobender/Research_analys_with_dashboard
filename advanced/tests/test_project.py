# -*- coding: utf-8 -*-
"""Тесты подпроекта: данные, критерии, скоринг и сам дашборд.

Запуск из корня репозитория:
    python -m pytest advanced/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ADV = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ADV))

from src import data as D        # noqa: E402
from src import scoring as SC    # noqa: E402
from src import stats as ST      # noqa: E402


@pytest.fixture(scope='module')
def df() -> pd.DataFrame:
    return D.load()


# --------------------------------------------------------------------------
# данные
# --------------------------------------------------------------------------
def test_данные_проходят_валидацию(df):
    D.assert_sane(df)


def test_дубликаты_по_имени_и_адресу_вычищены(df):
    assert not df.duplicated(subset=['name_norm', 'address_norm']).any()


def test_аббревиатуры_округов(df):
    assert D.district_abbr(D.CENTER) == 'ЦАО'
    assert D.district_abbr('Юго-Западный административный округ') == 'ЮЗАО'
    # в фильтрах подписи должны быть короткими, иначе чипы не помещаются
    assert df['district_abbr'].str.len().max() <= 4
    assert df['district_abbr'].nunique() == df['district'].nunique()


def test_источник_данных_по_умолчанию_синтетический():
    assert D.has_synthetic()
    assert D.resolve_dir(synthetic=True) == D.SYNTHETIC_DIR


def test_отсутствие_настоящих_данных_даёт_понятную_ошибку():
    if D.has_real():
        pytest.skip('настоящие данные на месте — проверять нечего')
    with pytest.raises(FileNotFoundError, match='datasets_real'):
        D.load(synthetic=False)


def test_валидатор_ловит_битые_данные(df):
    broken = df.copy()
    broken.loc[broken.index[0], 'rating'] = 9.9
    with pytest.raises(AssertionError):
        D.assert_sane(broken)


# --------------------------------------------------------------------------
# статистика
# --------------------------------------------------------------------------
def test_поправка_холма_не_ослабляет_p_value(df):
    pw = ST.pairwise_rating(df)
    assert (pw['p_holm'] >= pw['p-value'] - 1e-12).all()
    assert pw['p_holm'].is_monotonic_increasing  # таблица отсортирована по p


def test_размер_эффекта_нулевой_на_одинаковых_выборках():
    x = np.random.default_rng(0).normal(size=500)
    assert abs(ST.rank_biserial(x, x)) < 0.05


def test_бутстрэп_интервал_накрывает_медиану():
    x = np.random.default_rng(1).normal(100, 15, 400)
    lo, hi = ST.bootstrap_ci(x)
    assert lo < np.median(x) < hi


def test_сводка_покрывает_все_гипотезы(df):
    s = ST.summary(df)
    assert len(s) == 4
    assert s['вывод'].isin(['H0 отвергается', 'H0 не отвергается']).all()


# --------------------------------------------------------------------------
# скоринг
# --------------------------------------------------------------------------
def test_оценка_в_границах_шкалы(df):
    m = SC.score(df)
    assert not m.empty
    assert m['score'].between(0, 100).all()


def test_порог_надёжности_отсекает_мелкие_пары(df):
    assert (SC.build_matrix(df, min_objects=100)['n'] >= 100).all()


def test_вклады_факторов_дают_итоговую_оценку(df):
    m = SC.score(df)
    row = m.iloc[0]
    assert abs(SC.explain(row)['вклад в оценку'].sum() - row['score']) < 0.5


def test_веса_меняют_ранжирование(df):
    only_competition = SC.score(df, {f: 0 for f in SC.FACTORS} | {'competition': 1})
    only_revenue = SC.score(df, {f: 0 for f in SC.FACTORS} | {'revenue': 1})
    # при весе только на конкуренцию лидирует самая пустая ниша
    assert only_competition.iloc[0]['n'] == only_competition['n'].min()
    # при весе только на выручку — самая дорогая
    assert only_revenue.iloc[0]['median_bill'] == only_revenue['median_bill'].max()


def test_нулевые_веса_отвергаются(df):
    with pytest.raises(ValueError):
        SC.score(df, {f: 0 for f in SC.FACTORS})


# --------------------------------------------------------------------------
# дашборд
# --------------------------------------------------------------------------
@pytest.fixture(scope='module')
def app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ADV / 'app' / 'dashboard.py'), default_timeout=120)
    return at.run()


def test_дашборд_запускается_без_ошибок(app):
    assert not app.exception


def test_тумблер_синтетики_виден_и_предупреждение_на_месте(app):
    tog = app.toggle('f_synthetic')
    assert tog.label == 'Синтетические данные'
    assert tog.value is True
    assert any('Синтетические данные' in w.value for w in app.warning)


def test_по_умолчанию_показан_весь_рынок(app, df):
    assert app.metric[0].value == f'{len(df):,}'.replace(',', ' ')


def test_фильтр_округа_сужает_выборку(app, df):
    at = app.multiselect('f_districts').select(D.CENTER).run()
    assert not at.exception
    expected = (df['district'] == D.CENTER).sum()
    assert at.metric[0].value == f'{expected:,}'.replace(',', ' ')


def test_сброс_фильтров_возвращает_весь_рынок(app, df):
    at = app.multiselect('f_districts').select(D.CENTER).run()
    at = at.button[0].click().run()
    assert at.metric[0].value == f'{len(df):,}'.replace(',', ' ')


def test_в_подписях_нет_эмодзи():
    import re
    emoji = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')
    for p in [ADV / 'app' / 'dashboard.py', ADV / 'README.md',
              ADV / 'src' / 'scoring.py', ADV / 'src' / 'stats.py']:
        assert not emoji.search(p.read_text(encoding='utf-8')), p.name
