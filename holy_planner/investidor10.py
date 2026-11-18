"""Acesso à carteira oficial do Investidor10; não importa nem altera operações.

Cada pessoa informa o link público da própria carteira nas configurações.
Instalações novas começam no controle local, sem carteira vinculada.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

EXAMPLE_WALLET = 'https://investidor10.com.br/wallet/public/123456'
SECTIONS = {
    'summary': ('', 'Resumo'),
    'positions': ('positions', 'Posições'),
    'earnings': ('earnings', 'Proventos'),
    'patrimony': ('patrimony', 'Patrimônio'),
    'return': ('return', 'Rentabilidade'),
    'entries': ('entries', 'Lançamentos'),
}


def wallet_url(value):
    """Normaliza apenas URLs públicas deste provedor, sem parâmetros externos."""
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError('Informe o link público da carteira do Investidor10.')
    value = value.strip()
    if re.fullmatch(r'[1-9][0-9]{0,19}', value):
        value = 'https://investidor10.com.br/wallet/public/' + value
    parts = urlsplit(value)
    match = re.fullmatch(
        r'/wallet/public/([1-9][0-9]{0,19})(?:/(positions|earnings|patrimony|return|entries))?/?',
        parts.path,
    )
    if (parts.scheme != 'https' or
            parts.netloc.lower() not in ('investidor10.com.br', 'www.investidor10.com.br') or
            not match):
        raise ValueError(f'Use o link público da sua carteira, como {EXAMPLE_WALLET}.')
    return 'https://investidor10.com.br/wallet/public/' + match.group(1)


def section_url(value, section='summary'):
    if not isinstance(section, str) or section not in SECTIONS:
        raise ValueError('Seção do Investidor10 inválida.')
    suffix = SECTIONS[section][0]
    return wallet_url(value) + ('/' + suffix if suffix else '')


def initialize_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS investment_source (
        id INTEGER PRIMARY KEY CHECK(id=1),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
        wallet_url TEXT NOT NULL, label TEXT NOT NULL DEFAULT 'Minha carteira'
    )''')
    # Sem carteira padrão: o link é pessoal e informado por cada usuário.
    conn.execute("INSERT OR IGNORE INTO investment_source(id,enabled,wallet_url) VALUES (1,0,'')")
    conn.commit()


def configuration(db):
    result = dict(db.rows('SELECT enabled,wallet_url,label FROM investment_source WHERE id=1')[0])
    result['enabled'] = bool(result['enabled']) and bool(result['wallet_url'])
    result['configured'] = bool(result['wallet_url'])
    return result


def validate_configuration(payload):
    if not isinstance(payload, dict):
        raise ValueError('Configuração da carteira inválida.')
    enabled = payload.get('enabled')
    if not isinstance(enabled, (str, bool)) or enabled not in (True, False, '1', '0'):
        raise ValueError('Escolha Investidor10 ou controle local.')
    label = payload.get('label', 'Minha carteira')
    if not isinstance(label, str) or len(label) > 80:
        raise ValueError('O nome da carteira deve ter até 80 caracteres.')
    active = enabled is True or enabled == '1'
    raw = payload.get('wallet_url', '')
    if not active and (raw is None or (isinstance(raw, str) and not raw.strip())):
        url = ''  # Controle local sem carteira cadastrada.
    else:
        url = wallet_url(raw)
    return dict(enabled=int(active),
                wallet_url=url,
                label=label.strip() or 'Minha carteira')
