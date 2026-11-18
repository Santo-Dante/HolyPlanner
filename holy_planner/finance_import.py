"""Importação de extratos (OFX e CSV) com sugestão de categoria e detecção de duplicados."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

MAX_ROWS = 2000
KEYWORDS = [
    ('Alimentação', ('mercado', 'supermerc', 'padaria', 'ifood', 'restaurante', 'lanchon', 'pizzar', 'hortifruti', 'acougue', 'atacad', 'assai', 'carrefour', 'pao de acucar')),
    ('Transporte', ('uber', '99app', '99 pop', 'posto', 'combust', 'gasolina', 'estacion', 'metro', 'onibus', 'pedagio', 'sem parar', 'veloe', 'shell', 'ipiranga')),
    ('Saúde', ('farmacia', 'drogaria', 'droga', 'raia', 'hospital', 'clinica', 'medic', 'unimed', 'laborat', 'dentist', 'academia', 'smartfit')),
    ('Assinaturas', ('netflix', 'spotify', 'prime video', 'amazon prime', 'disney', 'hbo', 'max.com', 'youtube', 'apple.com', 'google one', 'assinatura', 'deezer', 'globoplay')),
    ('Moradia', ('aluguel', 'condominio', 'energia', 'enel', 'light', 'cemig', 'sabesp', 'copasa', 'agua', 'internet', 'vivo', 'claro', 'tim ', 'gas ', 'comgas')),
    ('Educação', ('escola', 'curso', 'faculdade', 'universidade', 'udemy', 'alura', 'livraria', 'livro')),
    ('Lazer', ('cinema', 'ingresso', 'show', 'bar ', 'viagem', 'hotel', 'airbnb', 'steam', 'playstation', 'xbox')),
]
INCOME_KEYWORDS = [('Salário', ('salario', 'folha', 'pagamento de salario', 'remuneracao')), ('Freelance', ('freela', 'freelance', 'servico prestado'))]


def normalize(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().casefold()
    return ' '.join(re.sub(r'[^a-z0-9 ]+', ' ', text).split())


def title_key(text):
    """Chave para reconhecer o mesmo estabelecimento: sem números e datas."""
    words = [w for w in normalize(text).split() if not w.isdigit()]
    return ' '.join(words[:4])


def suggest_category(history, title, kind):
    """history: lista de (title, category, kind). Prefere o que você já usou para o mesmo título."""
    key = title_key(title)
    counts = {}
    for past_title, category, past_kind in history:
        if past_kind == kind and key and title_key(past_title) == key:
            counts[category] = counts.get(category, 0) + 1
    if counts:
        return max(counts, key=counts.get)
    plain = ' ' + normalize(title) + ' '
    for category, words in (INCOME_KEYWORDS if kind == 'income' else KEYWORDS):
        if any(word in plain for word in words):
            return category
    return 'Outros'


def parse_amount(raw):
    value = str(raw or '').strip().replace('R$', '').replace(' ', '').replace(' ', '')
    negative = value.startswith('(') and value.endswith(')')
    value = value.strip('()')
    if value.endswith('-'):
        negative, value = True, value[:-1]
    if not value:
        return None
    if ',' in value and '.' in value:
        value = value.replace('.', '').replace(',', '.') if value.rfind(',') > value.rfind('.') else value.replace(',', '')
    elif ',' in value:
        value = value.replace('.', '').replace(',', '.')
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    cents = int((amount * 100).quantize(Decimal('1')))
    return -cents if negative else cents


def parse_date(raw):
    value = str(raw or '').strip()
    for pattern, order in ((r'(\d{4})-(\d{2})-(\d{2})', 'ymd'), (r'(\d{2})/(\d{2})/(\d{4})', 'dmy'), (r'(\d{2})/(\d{2})/(\d{2})$', 'dmy2'),
                           (r'(\d{2})-(\d{2})-(\d{4})', 'dmy'), (r'(\d{2})\.(\d{2})\.(\d{4})', 'dmy'), (r'^(\d{4})(\d{2})(\d{2})', 'ymd')):
        match = re.search(pattern, value)
        if match:
            a, b, c = match.groups()
            try:
                if order == 'ymd':
                    return date(int(a), int(b), int(c))
                return date(2000 + int(c) if order == 'dmy2' else int(c), int(b), int(a))
            except ValueError:
                return None
    return None


def parse_ofx(text):
    rows = []
    for block in re.findall(r'<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|</BANKTRANLIST>)', text, re.S | re.I):
        def tag(name):
            match = re.search(rf'<{name}>([^<\r\n]*)', block, re.I)
            return match.group(1).strip() if match else ''
        day, amount = parse_date(tag('DTPOSTED')), parse_amount(tag('TRNAMT'))
        if day and amount:
            title = tag('MEMO') or tag('NAME') or 'Lançamento importado'
            rows.append(dict(day=day, amount=amount, title=title, ref=tag('FITID')))
    return rows


HEADERS = {
    'day': ('data', 'date', 'data lancamento', 'data da transacao', 'data movimento', 'dt'),
    'title': ('descricao', 'description', 'historico', 'title', 'titulo', 'lancamento', 'estabelecimento', 'memo', 'detalhes', 'identificador'),
    'amount': ('valor', 'amount', 'value', 'valor r', 'valor rs', 'quantia'),
    'credit': ('credito', 'entrada', 'credit'),
    'debit': ('debito', 'saida', 'debit'),
}


def parse_csv(text):
    sample = text[:5000]
    delimiter = max((';', ',', '\t'), key=sample.count)
    reader = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header_index, columns = None, {}
    for index, row in enumerate(reader[:15]):
        names = [normalize(cell) for cell in row]
        found = {}
        for field, options in HEADERS.items():
            for position, name in enumerate(names):
                if name in options or any(name.startswith(option + ' ') for option in options):
                    found.setdefault(field, position)
        if 'day' in found and ('amount' in found or 'credit' in found or 'debit' in found):
            header_index, columns = index, found
            break
    if header_index is None:
        raise ValueError('Não encontrei as colunas de data e valor. O arquivo precisa de um cabeçalho como "Data;Descrição;Valor".')
    rows = []
    for row in reader[header_index + 1:]:
        if not any(cell.strip() for cell in row):
            continue
        get = lambda field: row[columns[field]] if field in columns and columns[field] < len(row) else ''
        day = parse_date(get('day'))
        if 'amount' in columns:
            amount = parse_amount(get('amount'))
        else:
            credit, debit = parse_amount(get('credit')) or 0, parse_amount(get('debit')) or 0
            amount = abs(credit) - abs(debit)
        if not day or not amount:
            continue
        rows.append(dict(day=day, amount=amount, title=get('title').strip() or 'Lançamento importado', ref=''))
    return rows


def parse_statement(text, filename=''):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('O arquivo está vazio.')
    if len(text) > 1_500_000:
        raise ValueError('Arquivo muito grande. Importe um período menor (até cerca de 1,5 MB).')
    is_ofx = filename.lower().endswith(('.ofx', '.qfx')) or '<OFX>' in text[:4000].upper() or 'OFXHEADER' in text[:400].upper()
    rows = parse_ofx(text) if is_ofx else parse_csv(text)
    if not rows:
        raise ValueError('Nenhum lançamento foi encontrado no arquivo.')
    if len(rows) > MAX_ROWS:
        raise ValueError(f'O arquivo tem mais de {MAX_ROWS} lançamentos. Importe um período menor.')
    return rows


def import_key(day, cents, title, ref):
    raw = f'{day}|{cents}|{normalize(title)}|{ref}'
    return hashlib.sha1(raw.encode()).hexdigest()[:24]
