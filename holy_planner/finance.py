"""Controle financeiro local: valores inteiros em centavos, sem serviços externos."""
from __future__ import annotations

import calendar
import csv
import io
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

KINDS = {
    "income": "Entrada", "expense": "Saída", "investment": "Aporte",
    "redemption": "Resgate", "yield": "Rendimento recebido",
}
CASH_SIGN = {"income": 1, "expense": -1, "investment": -1, "redemption": 1, "yield": 1}
CATEGORIES = ("Salário", "Freelance", "Moradia", "Alimentação", "Transporte",
              "Saúde", "Educação", "Lazer", "Assinaturas", "Investimentos", "Outros")
MAX_CENTS = 999_999_999_99


def initialize_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS finance_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN
                ('income','expense','investment','redemption','yield')),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            day TEXT NOT NULL, category TEXT NOT NULL COLLATE NOCASE,
            account TEXT NOT NULL DEFAULT '', asset TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('paid','pending')),
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_finance_day ON finance_transactions(day);
        CREATE INDEX IF NOT EXISTS idx_finance_status_day ON finance_transactions(status,day);
        CREATE TABLE IF NOT EXISTS finance_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT NOT NULL,
            category TEXT NOT NULL COLLATE NOCASE,
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            UNIQUE(month,category)
        );
        CREATE TABLE IF NOT EXISTS finance_settings (
            id INTEGER PRIMARY KEY CHECK(id=1),
            opening_cash_cents INTEGER NOT NULL DEFAULT 0,
            opening_invested_cents INTEGER NOT NULL DEFAULT 0 CHECK(opening_invested_cents >= 0)
        );
        INSERT OR IGNORE INTO finance_settings(id) VALUES (1);
    """)
    conn.commit()


def money_cents(value, *, positive=True, signed=False):
    """Aceita 1234,56, 1.234,56 ou 1234.56; rejeita precisão oculta e floats."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Informe o valor em reais, com no máximo duas casas decimais.")
    raw = str(value).strip()
    if len(raw) > 24:
        raise ValueError("Valor acima do limite permitido.")
    if ',' in raw:
        pattern = r"-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})"
        if not re.fullmatch(pattern, raw):
            raise ValueError("Valor inválido. Exemplo: 1.234,56.")
        raw = raw.replace('.', '').replace(',', '.')
    elif not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", raw):
        raise ValueError("Valor inválido. Exemplo: 1234,56.")
    try:
        amount = Decimal(raw)
        cents = int(amount * 100)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError("Valor inválido.") from exc
    if abs(cents) > MAX_CENTS or (positive and cents <= 0) or (not signed and cents < 0):
        raise ValueError("O valor deve ser maior que zero e até R$ 999.999.999,99." if positive
                         else "Saldo inválido ou acima de R$ 999.999.999,99.")
    return cents


def text_field(payload, key, limit, required=False):
    value = payload.get(key, '')
    if not isinstance(value, str):
        raise ValueError(f"Campo {key} inválido.")
    value = unicodedata.normalize('NFC', value.strip())
    if len(value) > limit or (required and not value):
        raise ValueError(f"Preencha {key} com até {limit} caracteres.")
    return value


def canonical_name(value, names):
    """Reutiliza a grafia de categorias e ativos, inclusive letras acentuadas."""
    key = unicodedata.normalize('NFC', value).casefold()
    return next((name for name in names if unicodedata.normalize('NFC', name).casefold() == key), value)


def month_bounds(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Mês inválido.")
    year, month = map(int, value.split('-'))
    first = date(year, month, 1)
    if not 1900 <= year <= 2100:
        raise ValueError("Escolha um ano entre 1900 e 2100.")
    return first.isoformat(), date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def validate_transaction(payload):
    if not isinstance(payload, dict):
        raise ValueError("Dados do lançamento inválidos.")
    kind, status = payload.get('kind'), payload.get('status', 'paid')
    if kind not in KINDS or status not in ('paid', 'pending'):
        raise ValueError("Tipo ou situação inválidos.")
    raw_day = payload.get('day')
    if not isinstance(raw_day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_day):
        raise ValueError("Informe uma data válida.")
    day = date.fromisoformat(raw_day)
    if not 1900 <= day.year <= 2100:
        raise ValueError("Escolha um ano entre 1900 e 2100.")
    if status == 'paid' and day > date.today():
        raise ValueError("Lançamentos futuros devem ficar como Previstos.")
    return dict(title=text_field(payload, 'title', 200, True), kind=kind,
                amount_cents=money_cents(payload.get('amount')), day=day.isoformat(),
                category=text_field(payload, 'category', 80, True),
                account=text_field(payload, 'account', 80),
                asset=text_field(payload, 'asset', 120, kind in ('investment', 'redemption', 'yield'))
                      if kind in ('investment', 'redemption', 'yield') else '',
                status=status, notes=text_field(payload, 'notes', 10000))


def summary(db, month):
    first, last = month_bounds(month)
    settings = dict(db.rows('SELECT * FROM finance_settings WHERE id=1')[0])
    totals = {k: 0 for k in KINDS}
    for row in db.rows("SELECT kind,SUM(amount_cents) AS total FROM finance_transactions "
                       "WHERE day BETWEEN ? AND ? AND status='paid' GROUP BY kind", (first, last)):
        totals[row['kind']] = row['total']
    accumulated = {k: 0 for k in KINDS}
    for row in db.rows("SELECT kind,SUM(amount_cents) AS total FROM finance_transactions "
                       "WHERE day<=? AND status='paid' GROUP BY kind", (last,)):
        accumulated[row['kind']] = row['total']
    cash = settings['opening_cash_cents'] + sum(accumulated[k] * CASH_SIGN[k] for k in KINDS)
    invested = settings['opening_invested_cents'] + accumulated['investment'] - accumulated['redemption']
    pending = [dict(r) for r in db.rows("SELECT * FROM finance_transactions "
               "WHERE day BETWEEN ? AND ? AND status='pending' ORDER BY day,id", (first, last))]
    transactions = [dict(r) for r in db.rows("SELECT * FROM finance_transactions "
                    "WHERE day BETWEEN ? AND ? ORDER BY day DESC,id DESC", (first, last))]
    categories = list(CATEGORIES)
    for row in db.rows("SELECT category FROM finance_transactions UNION SELECT category FROM finance_budgets"):
        if row['category'].casefold() not in {c.casefold() for c in categories}:
            categories.append(row['category'])
    expenses = [dict(r) for r in db.rows("SELECT category,SUM(amount_cents) AS total "
                "FROM finance_transactions WHERE day BETWEEN ? AND ? AND status='paid' AND kind='expense' "
                "GROUP BY category ORDER BY total DESC", (first, last))]
    budgets = []
    for row in db.rows("SELECT * FROM finance_budgets WHERE month=? ORDER BY category", (month,)):
        spent = next((c['total'] for c in expenses if c['category'].casefold() == row['category'].casefold()), 0)
        planned = sum(r['amount_cents'] for r in pending if r['kind']=='expense'
                      and r['category'].casefold()==row['category'].casefold())
        budgets.append({**dict(row), 'spent_cents': spent, 'pending_cents': planned})
    assets = [dict(r) for r in db.rows("SELECT asset, "
            "SUM(CASE WHEN kind='investment' THEN amount_cents WHEN kind='redemption' THEN -amount_cents ELSE 0 END) AS net_cents, "
            "SUM(CASE WHEN kind='yield' THEN amount_cents ELSE 0 END) AS yield_cents "
            "FROM finance_transactions WHERE status='paid' AND day<=? AND asset<>'' GROUP BY asset ORDER BY asset", (last,))]
    # Seis meses de fluxo realizado; os filtros da lista não alteram os totais.
    trend = []
    y, m = map(int, month.split('-'))
    for offset in range(5, -1, -1):
        index = y * 12 + m - 1 - offset
        key = f'{index // 12:04d}-{index % 12 + 1:02d}'
        start, end = month_bounds(key) if index//12 >= 1900 else ('0000-01-01', '0000-01-01')
        values = {k: 0 for k in KINDS}
        for r in db.rows("SELECT kind,SUM(amount_cents) AS total FROM finance_transactions "
                         "WHERE status='paid' AND day BETWEEN ? AND ? GROUP BY kind", (start, end)):
            values[r['kind']] = r['total']
        trend.append(dict(month=key, income_cents=values['income']+values['yield'], expense_cents=values['expense']))
    # Quanto ainda pode sair por dia até o fim do mês, depois de todos os previstos.
    today = date.today()
    current = today.strftime('%Y-%m') == month
    days_left = (date.fromisoformat(last) - today).days + 1 if current else 0
    projected = cash + sum(r['amount_cents'] * CASH_SIGN[r['kind']] for r in pending)
    daily = projected // days_left if current and days_left > 0 else None
    return dict(month=month, transactions=transactions, days_left=days_left, daily_allowance_cents=daily, categories=categories, totals=totals,
                cash_cents=cash, invested_cents=invested,
                net_month_cents=sum(totals[k]*CASH_SIGN[k] for k in KINDS),
                projected_cash_cents=cash+sum(r['amount_cents']*CASH_SIGN[r['kind']] for r in pending),
                pending_in_cents=sum(r['amount_cents'] for r in pending if CASH_SIGN[r['kind']]>0),
                pending_out_cents=sum(r['amount_cents'] for r in pending if CASH_SIGN[r['kind']]<0),
                overdue_count=db.rows("SELECT COUNT(*) AS n FROM finance_transactions WHERE status='pending' AND day<?", (date.today().isoformat(),))[0]['n'],
                settings=settings, expenses=expenses, budgets=budgets, assets=assets, trend=trend)


def export_csv(transactions):
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value
    output = io.StringIO(newline='')
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Data', 'Descrição', 'Tipo', 'Valor (R$)', 'Categoria', 'Conta', 'Investimento', 'Situação', 'Notas'])
    for r in transactions:
        writer.writerow([r['day'].split('-')[2]+'/'+r['day'].split('-')[1]+'/'+r['day'].split('-')[0],
                         safe(r['title']), KINDS[r['kind']], f"{r['amount_cents']//100},{r['amount_cents']%100:02d}",
                         safe(r['category']), safe(r['account']), safe(r['asset']),
                         'Efetivado' if r['status']=='paid' else 'Previsto', safe(r['notes'])])
    return output.getvalue()
