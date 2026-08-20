"""Geração do PDF do orçamento com **fpdf2** (100% Python, sem código C — compila
no Android sem problemas). Mantém o layout do sistema desktop original.

Estrutura:
  Página 1 (ORÇAMENTO): cabeçalho com logo + dados da empresa + nº/data,
      dados do cliente, tabela de itens, totais/desconto, condições comerciais,
      assinatura do prestador.
  Página 2 (ORDEM DE SERVIÇO, se preenchida): cabeçalho próprio, dados da
      contratante, condições da OS e o registro fotográfico.
"""
import os
from datetime import datetime

from util import fmt_moeda

# Obs.: o fpdf2 é importado de forma "preguiçosa" dentro de gerar_pdf() (e não no
# topo do módulo) para que, se por algum motivo a biblioteca falhar ao importar no
# Android, isso NÃO derrube a abertura do app — apenas a geração do PDF acusaria o
# erro, de forma controlada.

# --- cores ---
TEXT_PRIMARY = (43, 47, 56)
TEXT_SECONDARY = (92, 100, 114)
BORDER = (210, 216, 228)
ROW_EVEN = (246, 248, 252)
WHITE = (255, 255, 255)

# substituições p/ caracteres fora do Latin-1 (mantém o texto legível)
_REPL = {
    "—": "-", "–": "-", "•": "-", "“": '"', "”": '"', "‘": "'", "’": "'",
    "→": "->", "×": "x", "…": "...", " ": " ",
}


def S(t) -> str:
    """Sanitiza o texto para o conjunto Latin-1 usado pelas fontes core."""
    t = str(t if t is not None else "")
    for a, b in _REPL.items():
        t = t.replace(a, b)
    return t.encode("latin-1", "replace").decode("latin-1")


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _novo_pdf():
    """Cria e configura um documento fpdf2. O import é feito aqui (preguiçoso)."""
    from fpdf import FPDF
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(True, margin=15)
    return pdf


def _img_size(path, max_w, max_h):
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            w, h = im.size
        r = min(max_w / w, max_h / h)
        return w * r, h * r
    except Exception:
        return max_w, max_h


def gerar_pdf(caminho, dados, cor_primaria_hex="#4C6FD0", incluir_fotos=True):
    primary = _hex_rgb(cor_primaria_hex)
    pdf = _novo_pdf()
    cw = pdf.epw  # largura útil (content width)
    emp = dados["empresa"]
    cli = dados["cliente"]

    def secao(titulo):
        pdf.ln(1)
        pdf.set_fill_color(*primary)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(cw, 7, "  " + S(titulo), fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT_PRIMARY)
        pdf.ln(1.5)

    def linha_divisoria():
        pdf.set_draw_color(*primary)
        pdf.set_line_width(0.5)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.l_margin + cw, y)
        pdf.ln(3)

    def cabecalho(titulo_dir, num, subtitulo="", ref_label="Nº"):
        top = pdf.get_y()
        larg_dir = 50
        logo = emp.get("logo_path")
        x_texto = pdf.l_margin
        if logo and os.path.exists(logo):
            try:
                w, h = _img_size(logo, 28, 20)
                pdf.image(logo, x=pdf.l_margin, y=top, w=w, h=h)
                x_texto = pdf.l_margin + 30
            except Exception:
                pass
        # ---- bloco esquerdo: dados da empresa ----
        larg_emp = cw - (x_texto - pdf.l_margin) - larg_dir - 4
        pdf.set_xy(x_texto, top)
        pdf.set_text_color(*TEXT_SECONDARY)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(larg_emp, 5, S(emp.get("nome", "")),
                 new_x="LEFT", new_y="NEXT")
        pdf.set_x(x_texto)
        pdf.set_font("Helvetica", "", 8.5)
        info = []
        if emp.get("cnpj"):
            info.append(f"CNPJ: {emp['cnpj']}")
        if emp.get("endereco"):
            info.append(emp["endereco"])
        contato = " | ".join(x for x in [emp.get("telefone"), emp.get("email")] if x)
        if contato:
            info.append(contato)
        pdf.multi_cell(larg_emp, 4.3, S("\n".join(info)),
                       new_x="LMARGIN", new_y="NEXT")
        y_emp = pdf.get_y()
        # ---- bloco direito: título / (subtítulo) / número / data ----
        rx = pdf.l_margin + cw - larg_dir
        pdf.set_xy(rx, top)
        pdf.set_text_color(*primary)
        pdf.set_font("Helvetica", "B", 15)
        pdf.multi_cell(larg_dir, 6.5, S(titulo_dir), align="R",
                       new_x="LMARGIN", new_y="NEXT")
        if subtitulo:
            pdf.set_x(rx)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.multi_cell(larg_dir, 4.2, S(f"({subtitulo})"), align="R",
                           new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(rx)
        pdf.set_text_color(*TEXT_SECONDARY)
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(larg_dir, 4.6, S(f"{ref_label} {num}"), align="R",
                       new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(rx)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(larg_dir, 4.6, S("Data: " + datetime.now().strftime("%d/%m/%Y")),
                       align="R", new_x="LMARGIN", new_y="NEXT")
        y_dir = pdf.get_y()
        # desce até abaixo do bloco mais alto
        pdf.set_y(max(y_emp, y_dir, top + 22))
        linha_divisoria()

    def texto_bloco(txt):
        pdf.set_text_color(*TEXT_PRIMARY)
        for ln in txt.split("\n"):
            base = ln.strip()
            miolo = base.rstrip(":").replace("(", "").replace(")", "").replace(" ", "")
            eh_titulo = (base.endswith(":") and len(base) <= 60 and miolo.isupper()
                         and any(c.isalpha() for c in miolo))
            pdf.set_font("Helvetica", "B" if eh_titulo else "", 9)
            if base == "":
                pdf.ln(2.2)
            else:
                pdf.multi_cell(cw, 4.6, S(ln), new_x="LMARGIN", new_y="NEXT")

    def par_rotulo(rotulo, valor):
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*TEXT_PRIMARY)
        w = pdf.get_string_width(S(rotulo) + " ")
        pdf.cell(w, 5, S(rotulo))
        pdf.set_font("Helvetica", "", 9.5)
        pdf.multi_cell(cw - w, 5, S(valor or "-"),
                       new_x="LMARGIN", new_y="NEXT")

    # ================= PÁGINA 1: ORÇAMENTO =================
    pdf.add_page()
    subt = (emp.get("subtitulo") or "").strip()
    cabecalho("ORÇAMENTO", dados.get("numero", ""), subtitulo=subt)

    # Cliente
    secao("DADOS DO CLIENTE")
    par_rotulo("Nome:", cli.get("nome"))
    pdf.set_font("Helvetica", "", 9.5)
    par_rotulo("CPF/CNPJ:", cli.get("documento"))
    par_rotulo("Telefone:", cli.get("telefone"))
    par_rotulo("Endereço:", cli.get("endereco"))
    par_rotulo("E-mail:", cli.get("email"))
    pdf.ln(2)

    # Itens
    secao("ITENS DO ORÇAMENTO")
    _tabela_itens(pdf, dados["itens"], cw, primary)
    pdf.ln(2)

    # Totais
    _totais(pdf, dados, cw, primary)
    pdf.ln(3)

    # Condições comerciais
    if dados.get("termos"):
        secao("CONDIÇÕES COMERCIAIS E PRAZOS")
        texto_bloco(dados["termos"])
        pdf.ln(3)

    # Assinatura
    pdf.ln(4)
    pdf.set_text_color(*TEXT_PRIMARY)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.cell(cw, 5, "_________________________________________", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(cw, 5, "Assinatura do Prestador", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.cell(cw, 5, S(emp.get("nome", "")), align="C",
             new_x="LMARGIN", new_y="NEXT")
    if emp.get("cnpj"):
        pdf.cell(cw, 5, S(f"CNPJ: {emp['cnpj']}"), align="C",
                 new_x="LMARGIN", new_y="NEXT")

    # ================= PÁGINA 2: ORDEM DE SERVIÇO =================
    if dados.get("ordem_servico"):
        pdf.add_page()
        cabecalho("ORDEM DE\nSERVIÇO", dados.get("numero", ""), ref_label="Ref. Orç. Nº")
        # (subtítulo não se aplica à ordem de serviço)
        secao("DADOS DA CONTRATANTE")
        par_rotulo("Nome:", cli.get("nome"))
        par_rotulo("Documento:", cli.get("documento"))
        par_rotulo("Endereço:", cli.get("endereco"))
        par_rotulo("Telefone:", cli.get("telefone"))
        par_rotulo("E-mail:", cli.get("email"))
        pdf.ln(2)
        secao("CONDIÇÕES DA ORDEM DE SERVIÇO")
        texto_bloco(dados["ordem_servico"])
        pdf.ln(2)
        _fotos(pdf, dados, cw, primary, incluir_fotos, secao)
    else:
        _fotos(pdf, dados, cw, primary, incluir_fotos, secao)

    pdf.output(caminho)
    return caminho


def _tabela_itens(pdf, itens, cw, primary):
    col = [cw - (15 + 15 + 27 + 27), 15, 15, 27, 27]
    aligns = ["L", "C", "C", "R", "R"]
    cabec = ["Descrição", "Qtd", "Unid.", "Valor Unit.", "Total"]
    # cabeçalho
    pdf.set_fill_color(*primary)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 9.5)
    for w, a, t in zip(col, aligns, cabec):
        pdf.cell(w, 7, S(t), align=a, fill=True, border=0)
    pdf.ln(7)
    # linhas
    pdf.set_text_color(*TEXT_PRIMARY)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.2)
    for idx, it in enumerate(itens):
        qtd = it["quantidade"]
        qtd_fmt = int(qtd) if float(qtd).is_integer() else qtd
        valores = [S(it["descricao"]), str(qtd_fmt), S(it["unidade"]),
                   fmt_moeda(it["valor_unitario"]), fmt_moeda(it["total"])]
        # altura da linha depende da descrição
        pdf.set_font("Helvetica", "", 9.5)
        linhas_desc = pdf.multi_cell(col[0], 5, valores[0], dry_run=True,
                                     output="LINES", new_x="LEFT", new_y="TOP")
        alt = max(7, 5 * len(linhas_desc) + 2)
        # quebra de página se necessário
        if pdf.get_y() + alt > pdf.page_break_trigger:
            pdf.add_page()
        fill = (idx % 2 == 1)
        if fill:
            pdf.set_fill_color(*ROW_EVEN)
        x0, y0 = pdf.get_x(), pdf.get_y()
        # descrição (multi-linha)
        pdf.multi_cell(col[0], alt / max(1, len(linhas_desc)), valores[0],
                       border="B", align="L", fill=fill,
                       new_x="RIGHT", new_y="TOP", max_line_height=5)
        pdf.set_xy(x0 + col[0], y0)
        for w, a, v in zip(col[1:], aligns[1:], valores[1:]):
            pdf.cell(w, alt, v, align=a, border="B", fill=fill)
        pdf.ln(alt)


def _totais(pdf, dados, cw, primary):
    lab_w = cw - 55
    val_w = 55
    pdf.set_text_color(*TEXT_PRIMARY)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(lab_w, 6, "Subtotal:", align="R")
    pdf.cell(val_w, 6, fmt_moeda(dados["total_bruto"]), align="R",
             new_x="LMARGIN", new_y="NEXT")
    if dados.get("desconto_calculado"):
        if dados.get("desconto_tipo") == "percentual":
            rot = f"Desconto ({dados['desconto_valor']:g}%):"
        else:
            rot = "Desconto:"
        pdf.cell(lab_w, 6, S(rot), align="R")
        pdf.cell(val_w, 6, "- " + fmt_moeda(dados["desconto_calculado"]), align="R",
                 new_x="LMARGIN", new_y="NEXT")
    # linha + total
    y = pdf.get_y()
    pdf.set_draw_color(*primary)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin + lab_w, y, pdf.l_margin + cw, y)
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*primary)
    pdf.cell(lab_w, 8, "TOTAL:", align="R")
    pdf.cell(val_w, 8, fmt_moeda(dados["total_final"]), align="R",
             new_x="LMARGIN", new_y="NEXT")


def _fotos(pdf, dados, cw, primary, incluir, secao):
    if not (incluir and dados.get("fotos")):
        return
    validas = [p for p in dados["fotos"] if p and os.path.exists(p)]
    if not validas:
        return
    secao("REGISTRO FOTOGRÁFICO")
    col_w = (cw - 6) / 2
    max_h = 65
    i = 0
    while i < len(validas):
        par = validas[i:i + 2]
        # altura da linha = maior imagem
        alturas = []
        dims = []
        for p in par:
            w, h = _img_size(p, col_w, max_h)
            dims.append((w, h))
            alturas.append(h)
        row_h = max(alturas) + 4
        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()
        y0 = pdf.get_y()
        for j, p in enumerate(par):
            w, h = dims[j]
            x = pdf.l_margin + j * (col_w + 6) + (col_w - w) / 2
            try:
                pdf.image(p, x=x, y=y0, w=w, h=h)
            except Exception:
                pass
        pdf.set_y(y0 + row_h)
        i += 2
