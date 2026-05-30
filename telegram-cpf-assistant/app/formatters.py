from __future__ import annotations

"""Funções puras de parsing/formatação. Sem I/O, sem Telegram, sem SQL."""

import re
from datetime import date, datetime

_MONEY_RE = re.compile(r"^\d+([.,]\d{1,2})?$")

# Limite do Telegram por mensagem.
TELEGRAM_MAX = 4096


def now_local() -> str:
    """Timestamp local naive em ISO (YYYY-MM-DD HH:MM:SS)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_iso() -> str:
    return date.today().strftime("%Y-%m-%d")


def parse_money(raw: str) -> float | None:
    """Aceita '47.90' ou '47,90'. Devolve float ou None se inválido."""
    if not raw:
        return None
    raw = raw.strip()
    if not _MONEY_RE.match(raw):
        return None
    try:
        return round(float(raw.replace(",", ".")), 2)
    except ValueError:
        return None


def format_money(value: float | None) -> str:
    """Formata em padrão BR: 1234.5 -> 'R$ 1.234,50'."""
    if value is None:
        return "R$ 0,00"
    s = f"{value:,.2f}"  # 1,234.50
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"


def parse_due_date(raw: str) -> str | None:
    """Aceita YYYY-MM-DD, DD/MM, DD/MM/YYYY. Devolve ISO (YYYY-MM-DD) ou None."""
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m"):
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt == "%d/%m":
                dt = dt.replace(year=date.today().year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def split_long_message(text: str, limit: int = TELEGRAM_MAX) -> list[str]:
    """Quebra texto longo em pedaços <= limit, preferindo quebras de linha."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks
