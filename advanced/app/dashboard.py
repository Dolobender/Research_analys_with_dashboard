# -*- coding: utf-8 -*-
"""Дашборд аналитика по рынку общественного питания Москвы.

Запуск из корня репозитория:
    streamlit run advanced/app/dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import data as D           # noqa: E402
from src import scoring as SC       # noqa: E402
from src import stats as ST         # noqa: E402

st.set_page_config(page_title='Рынок общепита Москвы',
                   layout='wide', initial_sidebar_state='expanded')

PALETTE = px.colors.qualitative.Set2
TEMPLATE = 'plotly_white'


@st.cache_data(show_spinner='Загружаю данные…')
def get_data(synthetic: bool) -> pd.DataFrame:
    return D.load(synthetic=synthetic)


@st.cache_data
def get_scores(weights_key: tuple, min_objects: int, synthetic: bool) -> pd.DataFrame:
    return SC.score(get_data(synthetic), dict(weights_key), min_objects=min_objects)


# --------------------------------------------------------------------------
# сайдбар: источник данных
# --------------------------------------------------------------------------
sb = st.sidebar
sb.title('Рынок общепита Москвы')

real_available = D.has_real()
# без настоящих данных переключать нечего — тумблер остаётся включённым
# и заблокированным, но остаётся на виду: режим данных должен быть очевиден
synthetic = sb.toggle(
    'Синтетические данные', value=True, key='f_synthetic',
    disabled=not real_available,
    help=('Настоящие CSV не найдены. Положите `rest_info.csv` и `rest_price.csv` '
          f'в `{D.REAL_DIR.name}/` — тумблер станет активным.'
          if not real_available else
          f'Выключите, чтобы читать настоящие данные из `{D.REAL_DIR.name}/`.'))
if not real_available:
    synthetic = True

sb.caption('Цифры выдуманы генератором `make_synthetic_data.py`. Методика '
           'настоящая, значения — нет.' if synthetic
           else f'Настоящие данные из `{D.REAL_DIR.name}/`.')

try:
    df_all = get_data(synthetic)
except FileNotFoundError as err:
    st.error(str(err))
    st.stop()

# --------------------------------------------------------------------------
# сайдбар: фильтры
# --------------------------------------------------------------------------
sb.divider()

# в фильтрах — аббревиатуры («ЮЗАО»): полные названия дают по чипу на строку
# и виджет разрастается на пол-экрана. На графиках остаётся «Юго-Западный АО».
abbr = dict(zip(df_all['district'], df_all['district_abbr']))
districts = sorted(abbr, key=lambda d: abbr[d])
categories = sorted(df_all['category'].unique())
prices = [p for p in D.PRICE_ORDER if p in set(df_all['price'].dropna())]

FILTER_KEYS = ('f_chain', 'f_rating', 'f_districts', 'f_categories', 'f_prices')

# компактные фильтры идут первыми: списки-мультиселекты растут вниз и
# прятали бы их под собой
chain_filter = sb.radio('Тип заведения', ['Все', 'Сетевые', 'Несетевые'],
                        horizontal=True, key='f_chain')
rating_min, rating_max = sb.slider('Рейтинг', 0.0, 5.0, (0.0, 5.0), 0.1,
                                   key='f_rating')

sb.divider()
sb.caption('Срез рынка — пустое поле значит «все»')

# пустой выбор = «все»: так виджеты не забиты чипами по умолчанию
sel_districts = sb.multiselect('Округа', districts, format_func=lambda d: abbr[d],
                               placeholder='Все округа',
                               key='f_districts') or districts
sel_categories = sb.multiselect('Категории', categories,
                                placeholder='Все категории',
                                key='f_categories') or categories
sel_prices = sb.multiselect('Ценовой сегмент', prices,
                            placeholder='Все сегменты', key='f_prices') or prices

mask = (df_all['district'].isin(sel_districts)
        & df_all['category'].isin(sel_categories)
        & df_all['rating'].between(rating_min, rating_max)
        & (df_all['price'].isin(sel_prices) | df_all['price'].isna()))
if chain_filter != 'Все':
    mask &= df_all['chain_type'] == chain_filter

df = df_all[mask]

sb.divider()
if df.empty:
    sb.error('Под фильтры не попало ни одного заведения.')
    st.warning('Под выбранные фильтры не попало ни одного заведения. Ослабьте условия.')
    st.stop()

sb.metric('Отобрано заведений', f'{len(df):,}'.replace(',', ' '),
          delta=(f'{len(df) - len(df_all):+,}'.replace(',', ' ')
                 if len(df) != len(df_all) else 'весь рынок'),
          delta_color='off' if len(df) == len(df_all) else 'normal')

if sb.button('Сбросить фильтры', width='stretch',
             disabled=len(df) == len(df_all)):
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)
    st.rerun()

# --------------------------------------------------------------------------
# KPI-плитки
# --------------------------------------------------------------------------
st.title('Дашборд: рынок общественного питания Москвы')

if synthetic:
    # плашка на самом видном месте: без неё числа ниже выглядят как настоящие
    st.warning('**Синтетические данные.** Все цифры на этой странице сгенерированы '
               '`make_synthetic_data.py` по схеме и распределениям исходного '
               'исследования. Методика расчётов настоящая, значения — выдуманные; '
               'ссылаться на них как на данные о рынке Москвы нельзя.')

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric('Заведений', f'{len(df):,}'.replace(',', ' '))
k2.metric('Медианный чек', f"{df['middle_avg_bill'].median():,.0f} ₽".replace(',', ' ')
          if df['middle_avg_bill'].notna().any() else '—')
k3.metric('Средний рейтинг', f"{df['rating'].mean():.2f}")
k4.metric('Доля сетей', f"{df['chain'].mean() * 100:.1f}%")
k5.metric('Круглосуточных', f"{df['is_24_7'].mean() * 100:.1f}%")

tab_market, tab_score, tab_stats, tab_chains, tab_data = st.tabs(
    ['Рынок', 'Скоринг локаций', 'Проверка гипотез', 'Сети', 'Данные'])

# --------------------------------------------------------------------------
# вкладка «Рынок»
# --------------------------------------------------------------------------
with tab_market:
    c1, c2 = st.columns(2)

    with c1:
        cnt = df['category'].value_counts().reset_index()
        cnt.columns = ['Категория', 'Заведений']
        fig = px.bar(cnt.sort_values('Заведений'), x='Заведений', y='Категория',
                     orientation='h', template=TEMPLATE,
                     color='Заведений', color_continuous_scale='Teal',
                     title='Заведения по категориям')
        fig.update_layout(coloraxis_showscale=False, height=380)
        st.plotly_chart(fig, width='stretch')

    with c2:
        cnt = df['district_short'].value_counts().reset_index()
        cnt.columns = ['Округ', 'Заведений']
        fig = px.bar(cnt.sort_values('Заведений'), x='Заведений', y='Округ',
                     orientation='h', template=TEMPLATE,
                     color='Заведений', color_continuous_scale='Purp',
                     title='Заведения по округам')
        fig.update_layout(coloraxis_showscale=False, height=380)
        st.plotly_chart(fig, width='stretch')

    c3, c4 = st.columns(2)

    with c3:
        heat = (df.pivot_table(index='district_short', columns='category',
                               values='id', aggfunc='count')
                  .fillna(0).astype(int))
        fig = px.imshow(heat, template=TEMPLATE, text_auto=True, aspect='auto',
                        color_continuous_scale='Blues',
                        labels=dict(x='Категория', y='Округ', color='Заведений'),
                        title='Карта насыщенности: округ × категория')
        fig.update_layout(height=460, coloraxis_showscale=False)
        st.plotly_chart(fig, width='stretch')

    with c4:
        bill = df.dropna(subset=['middle_avg_bill'])
        if bill.empty:
            st.info('Нет данных о чеке под текущими фильтрами.')
        else:
            order = (bill.groupby('district_short')['middle_avg_bill']
                         .median().sort_values(ascending=False).index)
            fig = px.box(bill, x='district_short', y='middle_avg_bill',
                         category_orders={'district_short': list(order)},
                         template=TEMPLATE, color='district_short',
                         color_discrete_sequence=PALETTE,
                         title='Средний чек по округам',
                         labels={'district_short': '', 'middle_avg_bill': 'Чек, ₽'})
            fig.update_layout(showlegend=False, height=460)
            st.plotly_chart(fig, width='stretch')

    c5, c6 = st.columns(2)

    with c5:
        fig = px.violin(df, x='category', y='rating', box=True, points=False,
                        template=TEMPLATE, color='category',
                        color_discrete_sequence=PALETTE,
                        title='Распределение рейтинга по категориям',
                        labels={'category': '', 'rating': 'Рейтинг'})
        fig.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig, width='stretch')

    with c6:
        share = (df.groupby('category')['chain'].mean().mul(100)
                   .sort_values().reset_index())
        share.columns = ['Категория', 'Доля сетей, %']
        fig = px.bar(share, x='Доля сетей, %', y='Категория', orientation='h',
                     template=TEMPLATE, color='Доля сетей, %',
                     color_continuous_scale='Oranges',
                     title='Насколько сегмент занят сетями')
        fig.add_vline(x=df['chain'].mean() * 100, line_dash='dash',
                      annotation_text='в среднем по срезу')
        fig.update_layout(coloraxis_showscale=False, height=420)
        st.plotly_chart(fig, width='stretch')

# --------------------------------------------------------------------------
# вкладка «Скоринг локаций»
# --------------------------------------------------------------------------
with tab_score:
    st.subheader('Где открывать заведение')
    st.caption('Каждая пара «округ × категория» оценивается по пяти факторам. '
               'Веса настраиваются — оценка пересчитывается мгновенно.')

    wcols = st.columns(5)
    weights = {}
    for col, f in zip(wcols, SC.FACTORS):
        weights[f] = col.slider(SC.FACTOR_LABELS[f], 0.0, 1.0,
                                float(SC.DEFAULT_WEIGHTS[f]), 0.05, key=f'w_{f}')
    min_objects = st.slider('Минимум заведений в паре (порог надёжности)',
                            10, 200, SC.MIN_OBJECTS, 10)

    if sum(weights.values()) == 0:
        st.warning('Хотя бы один вес должен быть больше нуля.')
        st.stop()

    scores = get_scores(tuple(sorted(weights.items())), min_objects, synthetic)
    scores = scores[scores['district'].isin(sel_districts)
                    & scores['category'].isin(sel_categories)]

    if scores.empty:
        st.info('Под фильтры не попало ни одной пары, прошедшей порог надёжности.')
    else:
        c1, c2 = st.columns([3, 2])

        with c1:
            top = scores.head(15).copy()
            top['label'] = (top['district']
                            .str.replace(' административный округ', ' АО', regex=False)
                            + ' · ' + top['category'])
            fig = px.bar(top.sort_values('score'), x='score', y='label',
                         orientation='h', template=TEMPLATE, color='score',
                         color_continuous_scale='Viridis',
                         title='Топ-15 связок «округ × категория»',
                         labels={'score': 'Оценка привлекательности', 'label': ''})
            fig.update_layout(height=560, coloraxis_showscale=False)
            st.plotly_chart(fig, width='stretch')

        with c2:
            pivot = scores.pivot_table(index='district', columns='category',
                                       values='score')
            pivot.index = pivot.index.str.replace(' административный округ', ' АО',
                                                  regex=False)
            fig = px.imshow(pivot, template=TEMPLATE, text_auto='.0f', aspect='auto',
                            color_continuous_scale='Viridis',
                            labels=dict(x='', y='', color='Оценка'),
                            title='Матрица оценок')
            fig.update_layout(height=560, coloraxis_showscale=False)
            st.plotly_chart(fig, width='stretch')

        st.dataframe(SC.readable(scores, top=None), width='stretch',
                     hide_index=True)

        st.markdown('#### Из чего складывается оценка')
        options = [f"{r['district']} · {r['category']} — {r['score']}"
                   for _, r in scores.head(30).iterrows()]
        pick = st.selectbox('Связка', options, index=0)
        row = scores.iloc[options.index(pick)]
        e1, e2 = st.columns([2, 3])
        with e1:
            st.dataframe(SC.explain(row, weights), width='stretch',
                         hide_index=True)
        with e2:
            expl = SC.explain(row, weights)
            fig = go.Figure(go.Scatterpolar(
                r=[float(row[f]) for f in SC.FACTORS] + [float(row[SC.FACTORS[0]])],
                theta=[SC.FACTOR_LABELS[f] for f in SC.FACTORS]
                      + [SC.FACTOR_LABELS[SC.FACTORS[0]]],
                fill='toself', name='Профиль'))
            fig.update_layout(template=TEMPLATE, height=380,
                              polar=dict(radialaxis=dict(range=[0, 1])),
                              title=f'Профиль факторов · итог {row["score"]}',
                              showlegend=False)
            st.plotly_chart(fig, width='stretch')
            st.caption('Сумма вкладов: '
                       f'{expl["вклад в оценку"].sum():.1f} из 100')

# --------------------------------------------------------------------------
# вкладка «Проверка гипотез»
# --------------------------------------------------------------------------
with tab_stats:
    st.subheader('Статистическая проверка выводов')
    st.caption('Непараметрические критерии: распределения чека и числа мест '
               'скошены, нормальность не выполняется. Уровень значимости α = 0.05.')

    st.dataframe(ST.summary(df_all), width='stretch', hide_index=True)

    with st.expander('H0: средний чек в ЦАО не отличается от остальных округов'):
        r = ST.test_center_vs_rest(df_all)
        m1, m2, m3 = st.columns(3)
        m1.metric('Медиана ЦАО', f"{r['медиана ЦАО']:.0f} ₽")
        m2.metric('Медиана остальные', f"{r['медиана остальные']:.0f} ₽")
        m3.metric('Разность', f"{r['разность медиан']:+.0f} ₽",
                  help=f"95% ДИ: {r['95% ДИ разности']}")
        st.json({k: (str(v) if isinstance(v, tuple) else v) for k, v in r.items()})

    with st.expander('H0: рейтинг одинаков во всех категориях'):
        st.json(ST.test_rating_by_category(df_all))
        st.markdown('**Попарные сравнения (поправка Холма)**')
        pw = ST.pairwise_rating(df_all)
        st.dataframe(pw, width='stretch', hide_index=True)
        st.caption(f'Значимых пар: {int(pw["значимо"].sum())} из {len(pw)}')

    with st.expander('H0: сетевость не зависит от категории'):
        st.json(ST.test_chain_vs_category(df_all))

    with st.expander('H0: рейтинг не связан со средним чеком'):
        st.json(ST.test_rating_vs_bill(df_all))
        sub = df_all[['rating', 'middle_avg_bill', 'category']].dropna()
        fig = px.scatter(sub.sample(min(2000, len(sub)), random_state=1),
                         x='middle_avg_bill', y='rating', color='category',
                         opacity=.5, template=TEMPLATE, trendline='lowess',
                         color_discrete_sequence=PALETTE,
                         labels={'middle_avg_bill': 'Средний чек, ₽',
                                 'rating': 'Рейтинг', 'category': ''})
        fig.update_layout(height=460)
        st.plotly_chart(fig, width='stretch')

# --------------------------------------------------------------------------
# вкладка «Сети»
# --------------------------------------------------------------------------
with tab_chains:
    chains = df[df['chain'] == 1]
    if chains.empty:
        st.info('В текущем срезе нет сетевых заведений.')
    else:
        top = (chains.groupby('name')
               .agg(Точек=('id', 'count'), Рейтинг=('rating', 'mean'),
                    Категория=('category', lambda x: x.mode().iat[0]),
                    Чек=('middle_avg_bill', 'median'))
               .sort_values('Точек', ascending=False).head(20).reset_index())
        top['Рейтинг'] = top['Рейтинг'].round(2)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(top.sort_values('Точек'), x='Точек', y='name',
                         orientation='h', color='Категория', template=TEMPLATE,
                         color_discrete_sequence=PALETTE,
                         title='Топ-20 сетей по числу точек',
                         labels={'name': ''})
            fig.update_layout(height=560)
            st.plotly_chart(fig, width='stretch')
        with c2:
            fig = px.scatter(top, x='Точек', y='Рейтинг', size='Точек',
                             color='Категория', hover_name='name',
                             template=TEMPLATE, color_discrete_sequence=PALETTE,
                             title='Масштаб против качества')
            fig.add_hline(y=chains['rating'].mean(), line_dash='dash',
                          annotation_text='средний рейтинг сетей')
            fig.update_layout(height=560)
            st.plotly_chart(fig, width='stretch')

        st.dataframe(top, width='stretch', hide_index=True)

# --------------------------------------------------------------------------
# вкладка «Данные»
# --------------------------------------------------------------------------
with tab_data:
    st.subheader('Качество данных')
    st.dataframe(D.quality_report(df_all), width='stretch')

    st.subheader('Срез под фильтрами')
    cols = ['name', 'category', 'district_short', 'rating', 'chain_type',
            'seats', 'price', 'middle_avg_bill', 'is_24_7']
    st.dataframe(df[cols].head(500), width='stretch', hide_index=True)
    st.download_button('Скачать срез в CSV',
                       df[cols].to_csv(index=False).encode('utf-8-sig'),
                       file_name='market_slice.csv', mime='text/csv')
