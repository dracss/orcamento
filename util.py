"""Funções utilitárias: formatação de moeda no padrão brasileiro."""


def fmt_br(valor) -> str:
    """999999.99 -> '999.999,99'"""
    try:
        valor = float(valor)
    except (ValueError, TypeError):
        valor = 0.0
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_moeda(valor) -> str:
    """999999.99 -> 'R$ 999.999,99'"""
    return f"R$ {fmt_br(valor)}"


def parse_moeda(texto) -> float:
    """'R$ 1.234,56' -> 1234.56"""
    t = str(texto).replace("R$", "").strip()
    if not t:
        return 0.0
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def parse_num(texto) -> float:
    """Aceita vírgula ou ponto como separador decimal."""
    try:
        return float(str(texto).replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0
