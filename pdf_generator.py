"""Geração do PDF do orçamento (ReportLab) — fiel ao layout do sistema desktop.

Estrutura do PDF:
  Página 1 (ORÇAMENTO): cabeçalho com logo + dados da empresa + nº/data,
      dados do cliente, tabela de itens, totais/desconto, condições comerciais,
      assinatura do prestador.
  Página 2 (ORDEM DE SERVIÇO, se preenchida): cabeçalho próprio, dados da
      contratante, condições da OS e o registro fotográfico.
"""
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak,
)
from reportlab.lib.units import mm

from util import fmt_moeda

TEXT_PRIMARY = "#2B2F38"
TEXT_SECONDARY = "#5C6472"
BORDER_COLOR = "#E3E8F0"
ROW_EVEN = "#F6F8FC"


def _imagem_redimensionada(path, max_w, max_h):
    from PIL import Image as PILImage
    pil = PILImage.open(path)
    w, h = pil.size
    ratio = min(max_w / w, max_h / h)
    return Image(path, width=w * ratio, height=h * ratio)


def gerar_pdf(caminho, dados, cor_primaria_hex="#4C6FD0", incluir_fotos=True):
    cor_primaria = colors.HexColor(cor_primaria_hex)
    cor_clara = colors.HexColor(ROW_EVEN)
    cor_texto = colors.HexColor(TEXT_PRIMARY)
    cor_secundaria = colors.HexColor(TEXT_SECONDARY)
    cor_borda = colors.HexColor(BORDER_COLOR)

    doc = SimpleDocTemplate(
        caminho, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=str(dados.get("numero", "")),
    )

    styles = getSampleStyleSheet()
    st_sub = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=9,
                            textColor=cor_secundaria, leading=13)
    st_branco = ParagraphStyle("Bco", parent=styles["Normal"], fontSize=11,
                               textColor=colors.white, leading=14)
    st_normal = ParagraphStyle("Nor", parent=styles["Normal"], fontSize=9.5,
                               textColor=cor_texto, leading=14)
    st_desc = ParagraphStyle("Des", parent=styles["Normal"], fontSize=9.5,
                             textColor=cor_texto, leading=12)
    st_termos = ParagraphStyle("Ter", parent=styles["Normal"], fontSize=9,
                               textColor=cor_texto, leading=14)

    largura = doc.width

    def secao(titulo):
        t = Table([[Paragraph(f"<b>{titulo}</b>", st_branco)]], colWidths=[largura])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cor_primaria),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def _texto_formatado(txt):
        linhas = []
        for ln in txt.split("\n"):
            base = ln.strip()
            miolo = base.rstrip(":").replace("(", "").replace(")", "").replace(" ", "")
            eh_titulo = (base.endswith(":") and len(base) <= 60 and miolo.isupper()
                         and any(c.isalpha() for c in miolo))
            linhas.append(f"<b>{ln}</b>" if eh_titulo else ln)
        return "<br/>".join(linhas)

    elementos = []
    emp = dados["empresa"]

    info_empresa = (f"<b>{emp.get('nome','')}</b><br/>"
                    f"CNPJ: {emp.get('cnpj','')}<br/>"
                    f"{emp.get('endereco','')}<br/>"
                    f"Tel: {emp.get('telefone','')} &nbsp;|&nbsp; {emp.get('email','')}")

    def montar_cabecalho(info_direita):
        col_logo = None
        logo = emp.get("logo_path")
        if logo and os.path.exists(logo):
            try:
                col_logo = _imagem_redimensionada(logo, 30 * mm, 22 * mm)
            except Exception:
                col_logo = None
        if col_logo is not None:
            cab = Table([[col_logo, Paragraph(info_empresa, st_sub), Paragraph(info_direita, st_sub)]],
                        colWidths=[32 * mm, largura - 32 * mm - 45 * mm, 45 * mm])
        else:
            cab = Table([[Paragraph(info_empresa, st_sub), Paragraph(info_direita, st_sub)]],
                        colWidths=[largura - 45 * mm, 45 * mm])
        cab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return [
            cab,
            Spacer(1, 6),
            Table([[""]], colWidths=[largura],
                  style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.2, cor_primaria)])),
            Spacer(1, 10),
        ]

    # ---- Página 1: cabeçalho do ORÇAMENTO ----
    subtitulo = (emp.get("subtitulo") or "").strip()
    titulo_orc = "ORÇAMENTO" + (f" ({subtitulo})" if subtitulo else "")
    info_numero = (f"<para align='right'><font size=14 color='{cor_primaria_hex}'><b>{titulo_orc}</b></font><br/>"
                   f"<b>Nº {dados.get('numero','')}</b><br/>"
                   f"Data: {datetime.now().strftime('%d/%m/%Y')}</para>")
    elementos.extend(montar_cabecalho(info_numero))

    # ---- Cliente ----
    cli = dados["cliente"]
    elementos.append(secao("DADOS DO CLIENTE"))
    elementos.append(Spacer(1, 4))
    info_cli = (f"<b>Nome:</b> {cli.get('nome','')}<br/>"
                f"<b>CPF/CNPJ:</b> {cli.get('documento') or '—'} &nbsp;&nbsp; "
                f"<b>Telefone:</b> {cli.get('telefone') or '—'}<br/>"
                f"<b>Endereço:</b> {cli.get('endereco') or '—'}<br/>"
                f"<b>E-mail:</b> {cli.get('email') or '—'}")
    elementos.append(Paragraph(info_cli, st_normal))
    elementos.append(Spacer(1, 12))

    # ---- Itens ----
    elementos.append(secao("ITENS DO ORÇAMENTO"))
    elementos.append(Spacer(1, 4))
    cabec = ["Descrição", "Qtd", "Unid.", "Valor Unit.", "Total"]
    linhas = [cabec]
    for it in dados["itens"]:
        qtd = it["quantidade"]
        qtd_fmt = int(qtd) if float(qtd).is_integer() else qtd
        linhas.append([
            Paragraph(str(it["descricao"]), st_desc),
            str(qtd_fmt),
            str(it["unidade"]),
            fmt_moeda(it["valor_unitario"]),
            fmt_moeda(it["total"]),
        ])
    col_w = [largura - (18 + 18 + 30 + 30) * mm, 18 * mm, 18 * mm, 30 * mm, 30 * mm]
    tabela = Table(linhas, colWidths=col_w, repeatRows=1)
    estilo_tab = [
        ("BACKGROUND", (0, 0), (-1, 0), cor_primaria),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, cor_borda),
    ]
    for i in range(1, len(linhas)):
        if i % 2 == 0:
            estilo_tab.append(("BACKGROUND", (0, i), (-1, i), cor_clara))
    tabela.setStyle(TableStyle(estilo_tab))
    elementos.append(tabela)
    elementos.append(Spacer(1, 8))

    # ---- Totais ----
    tot_linhas = [["Subtotal:", fmt_moeda(dados["total_bruto"])]]
    if dados.get("desconto_calculado"):
        if dados.get("desconto_tipo") == "percentual":
            rotulo = f"Desconto ({dados['desconto_valor']:g}%):"
        else:
            rotulo = "Desconto:"
        tot_linhas.append([rotulo, f"- {fmt_moeda(dados['desconto_calculado'])}"])
    tot_linhas.append(["TOTAL:", fmt_moeda(dados["total_final"])])
    tab_tot = Table(tot_linhas, colWidths=[largura - 55 * mm, 55 * mm])
    tab_tot.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("TEXTCOLOR", (0, -1), (-1, -1), cor_primaria),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, cor_primaria),
        ("TOPPADDING", (0, -1), (-1, -1), 6),
    ]))
    elementos.append(tab_tot)
    elementos.append(Spacer(1, 14))

    # ---- Condições comerciais ----
    if dados.get("termos"):
        elementos.append(secao("CONDIÇÕES COMERCIAIS E PRAZOS"))
        elementos.append(Spacer(1, 4))
        elementos.append(Paragraph(_texto_formatado(dados["termos"]), st_termos))
        elementos.append(Spacer(1, 18))

    # ---- Assinatura ----
    assinatura = (f"<para align='center'>_________________________________________<br/>"
                  f"<b>Assinatura do Prestador</b><br/>{emp.get('nome','')}<br/>"
                  f"CNPJ: {emp.get('cnpj','')}</para>")
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(assinatura, st_normal))

    def blocos_fotos():
        if not (incluir_fotos and dados.get("fotos")):
            return []
        col_foto = (largura - 8 * mm) / 2
        celulas = []
        for p in dados["fotos"]:
            if os.path.exists(p):
                try:
                    celulas.append(_imagem_redimensionada(p, col_foto, 70 * mm))
                except Exception:
                    pass
        if not celulas:
            return []
        blocos = [secao("REGISTRO FOTOGRÁFICO"), Spacer(1, 6)]
        for i in range(0, len(celulas), 2):
            par = celulas[i:i + 2]
            if len(par) == 1:
                par.append("")
            t_foto = Table([par], colWidths=[col_foto, col_foto])
            t_foto.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            blocos.append(t_foto)
        return blocos

    # ---- Ordem de serviço ----
    if dados.get("ordem_servico"):
        elementos.append(PageBreak())
        info_os = (f"<para align='right'><font size=14 color='{cor_primaria_hex}'><b>ORDEM DE SERVIÇO</b></font><br/>"
                   f"Ref. Orçamento Nº {dados.get('numero','')}<br/>"
                   f"Data: {datetime.now().strftime('%d/%m/%Y')}</para>")
        elementos.extend(montar_cabecalho(info_os))
        elementos.append(secao("DADOS DA CONTRATANTE"))
        elementos.append(Spacer(1, 4))
        info_contratante = (f"<b>Nome:</b> {cli.get('nome','')}<br/>"
                            f"<b>Documento:</b> {cli.get('documento') or '—'}<br/>"
                            f"<b>Endereço:</b> {cli.get('endereco') or '—'}<br/>"
                            f"<b>Telefone:</b> {cli.get('telefone') or '—'}<br/>"
                            f"<b>E-mail:</b> {cli.get('email') or '—'}")
        elementos.append(Paragraph(info_contratante, st_normal))
        elementos.append(Spacer(1, 12))
        elementos.append(secao("CONDIÇÕES DA ORDEM DE SERVIÇO"))
        elementos.append(Spacer(1, 4))
        elementos.append(Paragraph(_texto_formatado(dados["ordem_servico"]), st_termos))
        elementos.append(Spacer(1, 12))
        elementos.extend(blocos_fotos())
    else:
        elementos.extend(blocos_fotos())

    doc.build(elementos)
    return caminho
