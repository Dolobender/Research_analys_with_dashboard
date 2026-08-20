# -*- coding: utf-8 -*-
"""Сборка ноутбуков подпроекта из исходников.

Ноутбуки — производный артефакт: правится этот файл, ноутбуки пересобираются
и исполняются (см. `advanced/run_all.py`). Так текст и код живут в git-diff
по-человечески, а не одной строкой JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

KERNEL = {
    'kernelspec': {'display_name': 'Python 3 (ipykernel)', 'language': 'python',
                   'name': 'python3'},
    'language_info': {'name': 'python', 'file_extension': '.py',
                      'mimetype': 'text/x-python', 'pygments_lexer': 'ipython3'},
}


def md(text):
    return {'cell_type': 'markdown', 'metadata': {},
            'source': text.strip('\n').splitlines(keepends=True)}


def code(text):
    return {'cell_type': 'code', 'metadata': {}, 'execution_count': None,
            'outputs': [], 'source': text.strip('\n').splitlines(keepends=True)}


def write(path: Path, cells: list) -> None:
    nb = {'cells': cells, 'metadata': KERNEL, 'nbformat': 4, 'nbformat_minor': 5}
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
    print('собран', path.name)


BOOT = '''
%matplotlib inline
import sys
import warnings
from pathlib import Path

warnings.filterwarnings('ignore', category=FutureWarning)

# подпроект лежит в advanced/, общий код — в advanced/src/
ROOT = Path.cwd()
if ROOT.name != 'advanced':
    ROOT = ROOT / 'advanced'
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from src import data as D
from src import stats as ST
from src import scoring as SC

pd.set_option('display.width', 140)
pd.set_option('display.max_columns', 40)
sns.set_theme(style='whitegrid', palette='Set2')
plt.rcParams['figure.dpi'] = 110

df = D.load()
D.assert_sane(df)
print(f'Загружено и очищено: {len(df):,} заведений, {df.shape[1]} признаков'.replace(',', ' '))
'''

# ==========================================================================
# 01 — статистическая проверка
# ==========================================================================
NB1 = [
    md('''
# 01 · Статистическая проверка выводов

**Подпроект `advanced` к исследованию рынка общепита Москвы.**
Оригинальный ноутбук — `../Проект ИАД рынка еды.ipynb`.

В основном исследовании выводы сформулированы описательно: «различия между
категориями невелики, но статистически значимы», «средний чек в ЦАО выше».
Ни одно из этих утверждений там не проверено критерием. Здесь каждое
проверяется явно, с размером эффекта и доверительным интервалом — потому что
при выборке в 8 тысяч наблюдений значимым становится почти любое различие,
и один только p-value ничего не решает.

**Что проверяем**

| # | Нулевая гипотеза | Критерий |
|---|------------------|----------|
| 1 | Средний чек в ЦАО не отличается от остальных округов | Манна—Уитни |
| 2 | Рейтинг одинаков во всех категориях | Краскела—Уоллиса + попарные с поправкой Холма |
| 3 | Сетевость не зависит от категории | хи-квадрат Пирсона |
| 4 | Рейтинг не связан со средним чеком | корреляция Спирмена |

Критерии непараметрические: распределения чека и числа мест скошены вправо,
нормальность не выполняется. Уровень значимости α = 0.05.
'''),
    code(BOOT),
    md('''
## Сводка

Сначала — общая картина: что отвергается, а где эффект настолько мал,
что значимость не означает практической разницы.
'''),
    code('''
summary = ST.summary(df)
display(summary)
'''),
    md('''
## Гипотеза 1. Средний чек: ЦАО против остальных округов

H0: распределение среднего чека в Центральном округе не отличается от
распределения в остальных восьми округах.
'''),
    code('''
res = ST.test_center_vs_rest(df)
for k, v in res.items():
    print(f'{k:>22}: {v}')
'''),
    code('''
center = df.loc[df['is_center'], 'middle_avg_bill'].dropna()
rest = df.loc[~df['is_center'], 'middle_avg_bill'].dropna()

fig, ax = plt.subplots(1, 2, figsize=(14, 5))
sns.kdeplot(center, ax=ax[0], fill=True, label=f'ЦАО (n={len(center)})', clip=(0, 6000))
sns.kdeplot(rest, ax=ax[0], fill=True, label=f'Остальные (n={len(rest)})', clip=(0, 6000))
ax[0].axvline(center.median(), ls='--', c='C0')
ax[0].axvline(rest.median(), ls='--', c='C1')
ax[0].set(title='Распределение среднего чека', xlabel='Средний чек, ₽', ylabel='Плотность')
ax[0].legend()

lo, hi = res['95% ДИ разности']
ax[1].barh(['Разность медиан'], [res['разность медиан']],
           xerr=[[res['разность медиан'] - lo], [hi - res['разность медиан']]],
           color='C2', height=.4, capsize=8)
ax[1].axvline(0, c='k', lw=1)
ax[1].set(title='Разность медиан с 95% бутстрэп-интервалом', xlabel='₽')
plt.tight_layout()
plt.show()
'''),
    md('''
**Читаем результат.** Интервал не накрывает ноль — разница устойчива, а не
артефакт выборки. Размер эффекта (rank-biserial r) показывает, насколько
разделены распределения: значение около 0.3–0.5 означает средний эффект —
округа различаются заметно, но распределения сильно перекрываются, и
«дорогие» заведения есть за пределами центра.
'''),
    md('''
## Гипотеза 2. Рейтинг по категориям

H0: медианный рейтинг одинаков во всех восьми категориях. Общий критерий
Краскела—Уоллиса скажет только «где-то есть различие»; чтобы понять, между
какими именно категориями, нужны попарные сравнения — с поправкой на
множественность, иначе при 28 парах ложное срабатывание почти гарантировано.
'''),
    code('''
res2 = ST.test_rating_by_category(df)
for k, v in res2.items():
    print(f'{k:>24}: {v}')
'''),
    code('''
pw = ST.pairwise_rating(df)
display(pw.head(15))
print(f'\\nЗначимых пар после поправки Холма: {int(pw["значимо"].sum())} из {len(pw)}')
print(f'Было бы значимо без поправки: {int((pw["p-value"] < 0.05).sum())}')
'''),
    code('''
order = df.groupby('category')['rating'].median().sort_values(ascending=False).index
stats_tbl = df.groupby('category')['rating'].agg(['count', 'mean', 'median', 'std'])
ci = {c: ST.bootstrap_ci(g['rating'], func=np.mean) for c, g in df.groupby('category')}

fig, ax = plt.subplots(figsize=(12, 5))
means = stats_tbl.loc[order, 'mean']
lo = [means[c] - ci[c][0] for c in order]
hi = [ci[c][1] - means[c] for c in order]
ax.errorbar(range(len(order)), means, yerr=[lo, hi], fmt='o', capsize=6, ms=8)
ax.set_xticks(range(len(order)))
ax.set_xticklabels(order, rotation=30, ha='right')
ax.set(title='Средний рейтинг с 95% доверительным интервалом',
       ylabel='Рейтинг')
plt.tight_layout()
plt.show()

display(stats_tbl.loc[order].round(3))
'''),
    md('''
**Читаем результат.** eps² — доля дисперсии рангов, объяснённая категорией.
Значение около 0.01–0.03 означает: категория объясняет считанные проценты
разброса рейтинга. Различия реальны, но для инвестиционного решения
бесполезны — выбирать формат по ожидаемому рейтингу нельзя.
'''),
    md('''
## Гипотеза 3. Сетевость и категория
'''),
    code('''
res3 = ST.test_chain_vs_category(df)
for k, v in res3.items():
    print(f'{k:>28}: {v}')

table = pd.crosstab(df['category'], df['chain_type'], normalize='index').mul(100).round(1)
display(table.sort_values('Сетевые', ascending=False))
'''),
    md('''
## Гипотеза 4. Рейтинг и средний чек
'''),
    code('''
res4 = ST.test_rating_vs_bill(df)
for k, v in res4.items():
    print(f'{k:>24}: {v}')

sub = df[['rating', 'middle_avg_bill']].dropna()
fig, ax = plt.subplots(figsize=(11, 5))
sns.regplot(data=sub.sample(min(2000, len(sub)), random_state=1),
            x='middle_avg_bill', y='rating', lowess=True,
            scatter_kws=dict(alpha=.25, s=18), line_kws=dict(color='crimson'), ax=ax)
ax.set(title='Рейтинг против среднего чека (lowess-сглаживание)',
       xlabel='Средний чек, ₽', ylabel='Рейтинг')
plt.tight_layout()
plt.show()
'''),
    md('''
## Итог

Ключевая поправка к выводам основного исследования: **статистическая значимость
здесь почти везде достигается за счёт размера выборки, а не за счёт величины
эффекта.** Практически значима только разница в чеке между центром и
периферией. Различия рейтингов между категориями значимы формально, но
объясняют считанные проценты разброса — строить на них решение нельзя.

Отсюда следует и постановка задачи для следующего ноутбука: раз рейтинг
предсказать по доступным признакам нельзя, выбирать локацию нужно по тому,
что измеримо — насыщенность ниши, потенциал выручки и структура конкуренции.

→ **[02 · Скоринг локаций](02_Скоринг_локаций.ipynb)**
'''),
]

# ==========================================================================
# 02 — скоринг локаций
# ==========================================================================
NB2 = [
    md('''
# 02 · Скоринг локаций: где открывать заведение

**Подпроект `advanced` к исследованию рынка общепита Москвы.**

Основное исследование заканчивается рекомендациями в свободной форме:
«для премиального сегмента — ресторан в ЦАО, для масштабирования — кофейня
в спальных районах». Это разумно, но непроверяемо и не ранжировано.

Здесь те же соображения формализованы в оценку. Каждая пара
«округ × категория» — а их до 72 — получает балл от 0 до 100 по пяти факторам.
Веса факторов задаются явно, поэтому решение можно оспорить предметно:
не «мне кажется», а «вы поставили конкуренции вес 0.3, поставьте 0.5».
'''),
    code(BOOT),
    md('''
## Факторы

| Фактор | Что измеряет | Направление |
|--------|--------------|-------------|
| Свободность ниши | число заведений категории в округе | меньше — лучше |
| Потенциал выручки | медианный средний чек в паре | больше — лучше |
| Слабость конкурентов | 5 − средний рейтинг действующих | больше — лучше |
| Фрагментированность | доля несетевых заведений | больше — лучше |
| Размер рынка округа | всего заведений в округе (прокси трафика) | больше — лучше |

Все факторы приводятся к шкале 0–1 через min-max по всем парам, итог —
взвешенная сумма, умноженная на 100. Пары, где меньше 30 заведений,
отбрасываются: медианы по десятку наблюдений неустойчивы.
'''),
    code('''
matrix = SC.build_matrix(df)
print(f'Пар «округ × категория», прошедших порог надёжности: {len(matrix)} '
      f'из {df["district"].nunique() * df["category"].nunique()} возможных')
display(matrix.head())
'''),
    md('''
## Базовый расчёт

Веса по умолчанию отражают инвестора, который прежде всего избегает
перегретых ниш (0.30 на конкуренцию), затем смотрит на выручку (0.25),
а остальное делит между качеством конкурентов, фрагментацией и трафиком.
'''),
    code('''
scores = SC.score(df)
print('Веса по умолчанию:', SC.DEFAULT_WEIGHTS)
display(SC.readable(scores, top=15))
'''),
    code('''
pivot = scores.pivot_table(index='district', columns='category', values='score')
pivot.index = pivot.index.str.replace(' административный округ', ' АО', regex=False)

fig, ax = plt.subplots(figsize=(13, 7))
sns.heatmap(pivot, annot=True, fmt='.0f', cmap='viridis', linewidths=.5,
            cbar_kws={'label': 'Оценка привлекательности'}, ax=ax)
ax.set(title='Матрица привлекательности: округ × категория', xlabel='', ylabel='')
plt.tight_layout()
plt.show()
'''),
    md('''
## Разбор конкретной связки

Оценка бесполезна, если её нельзя объяснить. Раскладываем лидера на вклады
факторов — сумма вкладов и есть итоговый балл.
'''),
    code('''
best = scores.iloc[0]
print(f'{best["district"]} · {best["category"]} — оценка {best["score"]}\\n')
display(SC.explain(best))

fig, ax = plt.subplots(figsize=(9, 4))
e = SC.explain(best)
ax.barh(e['фактор'], e['вклад в оценку'], color=sns.color_palette('Set2'))
ax.set(title=f'Из чего складывается оценка · {best["district"]}, {best["category"]}',
       xlabel='Вклад в итоговый балл')
plt.tight_layout()
plt.show()
'''),
    md('''
## Чувствительность к весам

Главный вопрос к любой такой модели: не подогнаны ли веса под желаемый ответ.
Проверяем три разных профиля инвестора и смотрим, что остаётся в топе при всех.
'''),
    code('''
PROFILES = {
    'Осторожный (уходит от конкуренции)':
        {'competition': .50, 'revenue': .15, 'quality_gap': .10,
         'fragmentation': .15, 'traffic': .10},
    'Премиальный (идёт за чеком)':
        {'competition': .15, 'revenue': .50, 'quality_gap': .10,
         'fragmentation': .05, 'traffic': .20},
    'Масштабирующий (ищет трафик)':
        {'competition': .20, 'revenue': .15, 'quality_gap': .10,
         'fragmentation': .15, 'traffic': .40},
}

tops = {}
for name, w in PROFILES.items():
    s = SC.score(df, w)
    tops[name] = (s['district'].str.replace(' административный округ', ' АО', regex=False)
                  + ' · ' + s['category']).head(10).tolist()

display(pd.DataFrame(tops))
'''),
    code('''
sets = [set(v) for v in tops.values()]
stable = set.intersection(*sets)
print('Попадают в топ-10 при ВСЕХ трёх профилях инвестора:')
for s in sorted(stable):
    print('  •', s)
print(f'\\nУстойчивых связок: {len(stable)} из 10')
'''),
    md('''
Устойчивое пересечение — и есть настоящая рекомендация. Связки, которые
всплывают только при одном наборе весов, — это свойство весов, а не рынка.
'''),
    md('''
## Риск-профиль: оценка против насыщенности

Высокий балл при большой плотности заведений и высокий балл при пустом рынке —
разные истории. Первое означает «здесь есть спрос, но придётся драться»,
второе — «здесь свободно, но, возможно, не зря».
'''),
    code('''
scores['label'] = (scores['district'].str.replace(' административный округ', '', regex=False)
                   + '\\n' + scores['category'])
fig, ax = plt.subplots(figsize=(12, 7))
sns.scatterplot(data=scores, x='n', y='median_bill', size='score', hue='category',
                sizes=(40, 400), alpha=.8, palette='Set2', ax=ax)
for _, r in scores.head(6).iterrows():
    ax.annotate(r['label'], (r['n'], r['median_bill']), fontsize=8,
                xytext=(6, 6), textcoords='offset points')
ax.set(title='Насыщенность против чека (размер точки — итоговая оценка)',
       xlabel='Заведений в паре', ylabel='Медианный чек, ₽')
ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
plt.tight_layout()
plt.show()
'''),
    md('''
## Ограничения модели

Честный список того, чего эта оценка не знает:

- **Нет данных об арендных ставках.** Свободная ниша в ЦАО может быть свободна
  именно потому, что аренда убивает экономику. Это главный пробел.
- **Нет трафика.** Число заведений в округе — грубый прокси; реальные потоки
  зависят от метро, офисов и жилой застройки, а не от границ округа.
- **Округ — слишком крупная единица.** Внутри ЦАО Тверская и Таганка — разные
  рынки. Нужен уровень района или, лучше, изохрон пешей доступности.
- **Данные статичны.** Нет динамики открытий и закрытий, а выживаемость точки
  информативнее их количества.
- **Веса — экспертные.** Они не выведены из данных, потому что в данных нет
  целевой переменной (выручки). Это оценочная модель, а не предсказательная.

Отсюда следующий шаг: связать датасет с данными об аренде и пассажиропотоке
метро — тогда оценку можно будет заменить моделью на реальном отклике.

→ **Интерактивная версия:** `streamlit run advanced/app/dashboard.py` —
там веса двигаются слайдерами, а результат пересчитывается на лету.
'''),
]

if __name__ == '__main__':
    write(HERE / '01_Статистическая_проверка.ipynb', NB1)
    write(HERE / '02_Скоринг_локаций.ipynb', NB2)
