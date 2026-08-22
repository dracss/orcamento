# -*- coding: utf-8 -*-
"""Orçamentos JM — app Android (KivyMD) de orçamentos e ordens de serviço.

Porta o sistema desktop original (JM Serviços) para o celular, com:
  • Cadastro de clientes (CRUD + busca)
  • Orçamentos com itens, desconto, fotos, termos e ordem de serviço
  • Geração de PDF profissional (com registro fotográfico e OS)
  • Dashboard com métricas
  • Personalização: logomarca, nome/dados da empresa e cores/tema
  • Backup na nuvem (compartilhar para Google Drive / e-mail / WhatsApp) e
    restauração a partir de arquivo
"""
import os
import sys
import traceback
from datetime import datetime

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.utils import get_color_from_hex

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel, MDIcon
from kivy.uix.image import Image as KivyImage
from kivymd.uix.list import (
    OneLineListItem, TwoLineListItem, TwoLineAvatarIconListItem,
    ThreeLineAvatarIconListItem, IconLeftWidget, IconRightWidget,
)
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.textfield import MDTextField

from database import Database, termos_padrao, ordem_servico_padrao
from util import fmt_moeda, parse_num
from pdf_generator import gerar_pdf
import backup as backup_mod
from androidpicker import escolher_imagem, escolher_arquivo
from paths import shared_dir, is_android


# Paletas oferecidas na tela de configurações (nome KivyMD -> hex p/ o PDF)
PALETAS = {
    "Indigo": "#4C6FD0", "Blue": "#2196F3", "Teal": "#009688",
    "Green": "#2FA56C", "Orange": "#F2A93B", "DeepOrange": "#FF5722",
    "Red": "#C0392B", "Purple": "#9C27B0", "BlueGray": "#607D8B", "Brown": "#795548",
}
UNIDADES = ["un", "m", "m²", "m³", "km", "kg", "h", "dia", "vb", "serviço", "peça"]

# Cores de destaque dos cartões de métricas e dos status (visual moderno)
ACCENT_METRICAS = ["#4C6FD0", "#2FA56C", "#F2A93B", "#7E57C2"]
STATUS_CORES = {"Rascunho": "#9AA3B2", "Enviado": "#4A90D9",
                "Aprovado": "#2FA56C", "Recusado": "#C0392B"}


def _cor(hexs):
    return get_color_from_hex(hexs)


def _cor_alpha(hexs, a):
    c = list(get_color_from_hex(hexs))
    c[3] = a
    return c


# ---------------------------------------------------------------------------
# Registro de erros em arquivo — grava a causa de qualquer crash num arquivo
# recuperável (Android/data/<pacote>/files/OrcamentosJM/orcamentosjm_erro.txt),
# para diagnóstico quando não há acesso ao logcat.
# ---------------------------------------------------------------------------
def _crash_dir():
    try:
        from jnius import autoclass
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        ext = act.getExternalFilesDir(None)
        if ext is not None:
            d = os.path.join(ext.getAbsolutePath(), "OrcamentosJM")
            os.makedirs(d, exist_ok=True)
            return d
    except Exception:
        pass
    for env in ("ANDROID_PRIVATE", "EXTERNAL_STORAGE"):
        p = os.environ.get(env)
        if p and os.path.isdir(p):
            return p
    return os.getcwd()


def registrar_crash(txt):
    try:
        caminho = os.path.join(_crash_dir(), "orcamentosjm_erro.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(txt)
        print("CRASH salvo em:", caminho)
    except Exception as e:
        print("Falha ao salvar crash:", e)


def _excepthook(tipo, valor, tb):
    registrar_crash("".join(traceback.format_exception(tipo, valor, tb)))
    sys.__excepthook__(tipo, valor, tb)


sys.excepthook = _excepthook


# Captura QUALQUER erro em tempo de execução (no laço de eventos do Kivy),
# grava em arquivo e MOSTRA na tela num popup — em vez de fechar o app.
_erro_ja_mostrado = {"last": None}


def _instalar_captura_erros():
    from kivy.base import ExceptionHandler, ExceptionManager

    class _Handler(ExceptionHandler):
        def handle_exception(self, inst):
            tb = traceback.format_exc()
            registrar_crash(tb)
            # mostra cada erro DISTINTO (evita repetir o mesmo em looping)
            if tb != _erro_ja_mostrado["last"]:
                _erro_ja_mostrado["last"] = tb
                try:
                    from kivy.uix.scrollview import ScrollView
                    from kivy.uix.label import Label
                    from kivy.uix.popup import Popup
                    lbl = Label(text=tb, size_hint_y=None, halign="left", valign="top",
                                padding=(10, 10))
                    lbl.bind(width=lambda *a: setattr(lbl, "text_size", (lbl.width, None)),
                             texture_size=lambda *a: setattr(lbl, "height", lbl.texture_size[1]))
                    sv = ScrollView()
                    sv.add_widget(lbl)
                    Popup(title="Erro (tire um print e envie ao suporte)",
                          content=sv, size_hint=(0.95, 0.9)).open()
                except Exception:
                    pass
            return ExceptionManager.PASS

    ExceptionManager.add_handler(_Handler())


def make_field(hint, valor="", multiline=False, **kw):
    """Cria um MDTextField já no modo 'rectangle'.

    O texto inicial é aplicado no frame seguinte para evitar o bug do KivyMD
    1.1.1 em que o rótulo (hint) fica sobreposto ao valor quando definido na
    construção do widget.
    """
    from kivy.clock import Clock
    tf = MDTextField(hint_text=hint, mode="rectangle", multiline=multiline, **kw)
    if valor not in (None, ""):
        Clock.schedule_once(lambda dt, tf=tf, v=str(valor): setattr(tf, "text", v), 0)
    return tf

KV = '''
#:import get_color_from_hex kivy.utils.get_color_from_hex

<CampoTexto@MDTextField>:
    mode: "rectangle"
    size_hint_y: None
    height: "48dp"

MDScreenManager:
    id: root_sm

    MDScreen:
        name: "main"
        md_bg_color: app.theme_cls.bg_normal
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                id: appbar
                title: "Orçamentos JM"
                elevation: 3
                right_action_items: [["cloud-upload-outline", lambda x: app.tela_backup()], ["cog-outline", lambda x: app.ir_config()], ["exit-to-app", lambda x: app.sair()]]
            MDBottomNavigation:
                id: bottom_nav
                selected_color_background: app.theme_cls.primary_light
                text_color_active: app.theme_cls.primary_color

                MDBottomNavigationItem:
                    name: "tab_inicio"
                    text: "Início"
                    icon: "view-dashboard-outline"
                    on_tab_press: app.refresh_dashboard()
                    ScrollView:
                        MDBoxLayout:
                            id: dash_box
                            orientation: "vertical"
                            adaptive_height: True
                            padding: "12dp"
                            spacing: "12dp"

                MDBottomNavigationItem:
                    name: "tab_orcamentos"
                    text: "Orçamentos"
                    icon: "file-document-outline"
                    on_tab_press: app.refresh_orcamentos()
                    MDBoxLayout:
                        orientation: "vertical"
                        padding: "8dp"
                        spacing: "6dp"
                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"
                            size_hint_y: None
                            height: "56dp"
                            CampoTexto:
                                id: busca_orc
                                hint_text: "Buscar por nº ou cliente"
                                on_text: app.refresh_orcamentos()
                            MDRaisedButton:
                                text: "Novo"
                                icon: "plus"
                                on_release: app.novo_orcamento()
                        ScrollView:
                            MDList:
                                id: lista_orc

                MDBottomNavigationItem:
                    name: "tab_clientes"
                    text: "Clientes"
                    icon: "account-group-outline"
                    on_tab_press: app.refresh_clientes()
                    MDBoxLayout:
                        orientation: "vertical"
                        padding: "8dp"
                        spacing: "6dp"
                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"
                            size_hint_y: None
                            height: "56dp"
                            CampoTexto:
                                id: busca_cli
                                hint_text: "Buscar cliente"
                                on_text: app.refresh_clientes()
                            MDRaisedButton:
                                text: "Novo"
                                icon: "plus"
                                on_release: app.novo_cliente()
                        ScrollView:
                            MDList:
                                id: lista_cli

    MDScreen:
        name: "form_orcamento"
        md_bg_color: app.theme_cls.bg_normal
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                id: appbar_orc
                title: "Novo Orçamento"
                left_action_items: [["arrow-left", lambda x: app.voltar_main("tab_orcamentos")]]
                right_action_items: [["content-save-outline", lambda x: app.salvar_orcamento()], ["file-pdf-box", lambda x: app.gerar_pdf_orcamento()]]
            ScrollView:
                MDBoxLayout:
                    id: form_orc_box
                    orientation: "vertical"
                    adaptive_height: True
                    padding: "12dp"
                    spacing: "10dp"

    MDScreen:
        name: "form_cliente"
        md_bg_color: app.theme_cls.bg_normal
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Cliente"
                left_action_items: [["arrow-left", lambda x: app.voltar_main("tab_clientes")]]
                right_action_items: [["content-save-outline", lambda x: app.salvar_cliente_form()]]
            ScrollView:
                MDBoxLayout:
                    id: form_cli_box
                    orientation: "vertical"
                    adaptive_height: True
                    padding: "16dp"
                    spacing: "12dp"

    MDScreen:
        name: "ver_cliente"
        md_bg_color: app.theme_cls.bg_normal
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                id: appbar_vercli
                title: "Orçamentos do cliente"
                left_action_items: [["arrow-left", lambda x: app.voltar_main("tab_clientes")]]
            ScrollView:
                MDList:
                    id: lista_vercli

    MDScreen:
        name: "config"
        md_bg_color: app.theme_cls.bg_normal
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Configurações"
                left_action_items: [["arrow-left", lambda x: app.voltar_main("tab_inicio")]]
            ScrollView:
                MDBoxLayout:
                    id: config_box
                    orientation: "vertical"
                    adaptive_height: True
                    padding: "16dp"
                    spacing: "14dp"

    MDScreen:
        name: "backup"
        md_bg_color: app.theme_cls.bg_normal
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Backup na nuvem"
                left_action_items: [["arrow-left", lambda x: app.voltar_main("tab_inicio")]]
            ScrollView:
                MDBoxLayout:
                    id: backup_box
                    orientation: "vertical"
                    adaptive_height: True
                    padding: "16dp"
                    spacing: "14dp"
'''


class OrcamentosApp(MDApp):
    titulo_app = StringProperty("Orçamentos JM")

    def build(self):
        _instalar_captura_erros()
        self.db = Database()
        cfg = self.db.config()
        self.theme_cls.theme_style = cfg.get("tema", "Light")
        self.theme_cls.primary_palette = cfg.get("paleta", "Indigo")
        self._menu = None
        self.orc_editando = None      # id do orçamento em edição (ou None)
        self.itens_atuais = []        # itens do orçamento sendo editado
        self.fotos_atuais = []        # caminhos das fotos
        self.desconto_tipo = "valor"
        self.cli_editando = None
        root = Builder.load_string(KV)
        # Evita o "flash preto" ao trocar de tela: transição instantânea + fundo
        # da janela pintado com a cor do tema (nada de preto por trás).
        try:
            from kivy.uix.screenmanager import NoTransition
            root.transition = NoTransition()
            # a barra de abas (MDBottomNavigation) usa FadeTransition por padrão,
            # que funde passando pelo fundo (o "flash escuro"). Troca por instantânea.
            bn = root.ids.bottom_nav
            bn.transition = NoTransition
            bn.transition_duration = 0
        except Exception:
            pass
        try:
            from kivy.core.window import Window
            Window.clearcolor = self.theme_cls.bg_normal
        except Exception:
            pass
        return root

    def on_theme_change(self):
        try:
            from kivy.core.window import Window
            Window.clearcolor = self.theme_cls.bg_normal
        except Exception:
            pass

    def on_start(self):
        try:
            self._pedir_permissoes()
        except Exception:
            registrar_crash(traceback.format_exc())
        try:
            self.refresh_dashboard()
        except Exception:
            registrar_crash(traceback.format_exc())

    # ------------------------------------------------------------- utilidades
    def _pedir_permissoes(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
            ])
        except Exception:
            pass

    def toast(self, msg):
        try:
            from kivymd.toast import toast
            toast(msg)
        except Exception:
            print("TOAST:", msg)

    def _dialog(self, titulo, texto, on_ok=None, ok_text="OK", cancel=True):
        botoes = []
        if cancel:
            botoes.append(MDFlatButton(text="Cancelar", on_release=lambda x: self._d.dismiss()))

        def _ok(*_):
            self._d.dismiss()
            if on_ok:
                on_ok()
        botoes.append(MDRaisedButton(text=ok_text, on_release=_ok))
        self._d = MDDialog(title=titulo, text=texto, buttons=botoes)
        self._d.open()

    def voltar_main(self, aba=None):
        self.root.current = "main"
        if aba:
            self.root.ids.bottom_nav.switch_tab(aba)

    def ir_config(self):
        self.montar_config()
        self.root.current = "config"

    def sair(self):
        self._dialog("Sair do aplicativo", "Deseja realmente fechar o app?",
                     on_ok=self._fechar_app, ok_text="Sair")

    def _fechar_app(self):
        try:
            self.db.close()
        except Exception:
            pass
        self.stop()
        try:
            # no Android, encerra a atividade para fechar de fato
            from jnius import autoclass
            autoclass("org.kivy.android.PythonActivity").mActivity.finish()
        except Exception:
            pass

    # =====================================================================
    # DASHBOARD
    # =====================================================================
    def refresh_dashboard(self):
        box = self.root.ids.dash_box
        box.clear_widgets()
        m = self.db.metricas()
        emp = self.db.empresa()

        # ---- Cabeçalho colorido com logo + nome + data ----
        box.add_widget(self._cabecalho_dashboard(emp))

        # ---- Métricas (2 x 2) ----
        grid = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(12))
        linhas = [
            [("Orçamentos", str(m["orcamentos"]), "file-document-outline", ACCENT_METRICAS[0]),
             ("Clientes", str(m["clientes"]), "account-group", ACCENT_METRICAS[3])],
            [("Valor total", fmt_moeda(m["valor_total"]), "cash-multiple", ACCENT_METRICAS[1]),
             ("Aprovados", fmt_moeda(m["valor_aprovado"]), "check-decagram", ACCENT_METRICAS[2])],
        ]
        for par in linhas:
            row = MDBoxLayout(spacing=dp(12), size_hint_y=None, height=dp(104))
            for titulo, valor, icone, cor in par:
                row.add_widget(self._card_metrica(titulo, valor, icone, cor))
            grid.add_widget(row)
        box.add_widget(grid)

        # ---- Ações rápidas ----
        acoes = MDBoxLayout(spacing=dp(12), size_hint_y=None, height=dp(48))
        b1 = MDRaisedButton(text="Novo orçamento", icon="plus", size_hint_x=1)
        b1.bind(on_release=lambda x: self.novo_orcamento())
        b2 = MDRaisedButton(text="Novo cliente", icon="account-plus", size_hint_x=1,
                            md_bg_color=_cor(ACCENT_METRICAS[3]))
        b2.bind(on_release=lambda x: self.novo_cliente())
        acoes.add_widget(b1)
        acoes.add_widget(b2)
        box.add_widget(acoes)

        # ---- Recentes ----
        box.add_widget(MDLabel(text="Orçamentos recentes", font_style="H6",
                               bold=True, adaptive_height=True))
        recentes = self.db.listar_orcamentos()[:6]
        if not recentes:
            vazio = MDCard(size_hint_y=None, height=dp(90), radius=[dp(16)], elevation=0,
                           md_bg_color=_cor_alpha(ACCENT_METRICAS[0], 0.06),
                           padding=dp(14))
            vazio.add_widget(MDLabel(
                text="Nenhum orçamento ainda.\nToque em “Novo orçamento” para começar.",
                theme_text_color="Secondary", halign="center"))
            box.add_widget(vazio)
        else:
            for o in recentes:
                box.add_widget(self._card_orcamento(o))

        box.add_widget(MDFlatButton(text="Sair do aplicativo",
                                    theme_text_color="Custom",
                                    text_color=self.theme_cls.primary_color,
                                    pos_hint={"center_x": .5},
                                    on_release=lambda x: self.sair()))

    def _cabecalho_dashboard(self, emp):
        card = MDCard(size_hint_y=None, height=dp(96), radius=[dp(20)],
                      md_bg_color=self.theme_cls.primary_color, elevation=4,
                      padding=dp(14), spacing=dp(14))
        # círculo com logo ou ícone
        circ = MDCard(size_hint=(None, None), size=(dp(64), dp(64)), radius=[dp(32)],
                      md_bg_color=(1, 1, 1, 1), elevation=0, padding=dp(6))
        logo = emp.get("logo_path")
        if logo and os.path.exists(logo):
            circ.add_widget(KivyImage(source=logo, allow_stretch=True, keep_ratio=True))
        else:
            circ.add_widget(MDIcon(icon="office-building", halign="center",
                                   theme_text_color="Custom",
                                   text_color=self.theme_cls.primary_color, font_size="34sp"))
        card.add_widget(circ)
        texto = MDBoxLayout(orientation="vertical", spacing=dp(2))
        texto.add_widget(MDLabel(text=emp.get("nome") or "Sua Empresa",
                                 font_style="H6", bold=True, theme_text_color="Custom",
                                 text_color=(1, 1, 1, 1), shorten=True))
        sub = (emp.get("subtitulo") or "").strip()
        texto.add_widget(MDLabel(
            text=sub or datetime.now().strftime("Hoje é %d/%m/%Y"),
            theme_text_color="Custom", text_color=(1, 1, 1, 0.85), font_style="Caption",
            shorten=True))
        card.add_widget(texto)
        return card

    def _card_metrica(self, titulo, valor, icone, cor_hex):
        card = MDCard(orientation="vertical", padding=dp(14), radius=[dp(18)],
                      elevation=2, spacing=dp(6))
        circ = MDCard(size_hint=(None, None), size=(dp(40), dp(40)), radius=[dp(20)],
                      md_bg_color=_cor_alpha(cor_hex, 0.16), elevation=0)
        circ.add_widget(MDIcon(icon=icone, halign="center", theme_text_color="Custom",
                               text_color=_cor(cor_hex)))
        card.add_widget(circ)
        card.add_widget(MDLabel(text=valor, font_style="H6", bold=True, adaptive_height=True,
                                shorten=True))
        card.add_widget(MDLabel(text=titulo, theme_text_color="Secondary",
                                font_style="Caption", adaptive_height=True))
        return card

    def _chip_status(self, status):
        cor = STATUS_CORES.get(status, "#9AA3B2")
        chip = MDCard(size_hint=(None, None), height=dp(24), radius=[dp(12)],
                      md_bg_color=_cor_alpha(cor, 0.16), elevation=0,
                      padding=(dp(10), 0))
        lb = MDLabel(text=status or "Rascunho", theme_text_color="Custom",
                     text_color=_cor(cor), font_style="Caption", bold=True,
                     halign="center", valign="center")
        lb.bind(texture_size=lambda i, v: setattr(chip, "width", v[0] + dp(20)))
        chip.add_widget(lb)
        return chip

    def _card_orcamento(self, o, com_menu=False):
        card = MDCard(size_hint_y=None, height=dp(76), radius=[dp(16)], elevation=1,
                      padding=(dp(12), dp(8)), spacing=dp(10), ripple_behavior=True)
        card.bind(on_release=lambda w, oid=o["id"]: self.abrir_orcamento(oid))
        # ícone à esquerda
        circ = MDCard(size_hint=(None, None), size=(dp(44), dp(44)), radius=[dp(22)],
                      md_bg_color=_cor_alpha(ACCENT_METRICAS[0], 0.14), elevation=0,
                      pos_hint={"center_y": .5})
        circ.add_widget(MDIcon(icon="file-document-outline", halign="center",
                               theme_text_color="Custom", text_color=_cor(ACCENT_METRICAS[0])))
        card.add_widget(circ)
        meio = MDBoxLayout(orientation="vertical", pos_hint={"center_y": .5})
        meio.add_widget(MDLabel(text=o["numero"], bold=True, font_style="Subtitle1",
                                shorten=True))
        meio.add_widget(MDLabel(text=o.get("cliente_nome") or "Sem cliente",
                                theme_text_color="Secondary", font_style="Caption",
                                shorten=True))
        card.add_widget(meio)
        dire = MDBoxLayout(orientation="vertical", size_hint_x=None, width=dp(112),
                           pos_hint={"center_y": .5}, spacing=dp(4))
        dire.add_widget(MDLabel(text=fmt_moeda(o["total"]), bold=True, halign="right",
                                font_style="Subtitle2", shorten=True))
        linha_chip = MDBoxLayout(size_hint_y=None, height=dp(24))
        linha_chip.add_widget(MDBoxLayout())  # espaçador (empurra chip p/ direita)
        linha_chip.add_widget(self._chip_status(o.get("status", "Rascunho")))
        dire.add_widget(linha_chip)
        card.add_widget(dire)
        if com_menu:
            bt = MDIconButton(icon="dots-vertical", pos_hint={"center_y": .5})
            bt.bind(on_release=lambda w, oid=o["id"], num=o["numero"]: self.menu_orcamento(w, oid, num))
            card.add_widget(bt)
        return card

    # =====================================================================
    # LISTA DE ORÇAMENTOS
    # =====================================================================
    def refresh_orcamentos(self):
        if "busca_orc" not in self.root.ids:
            return
        filtro = self.root.ids.busca_orc.text.strip()
        lista = self.root.ids.lista_orc
        lista.clear_widgets()
        orcs = self.db.listar_orcamentos(filtro)
        lista.spacing = dp(8)
        lista.padding = [dp(4), dp(6), dp(4), dp(6)]
        if not orcs:
            lista.add_widget(OneLineListItem(text="Nenhum orçamento encontrado."))
            return
        for o in orcs:
            lista.add_widget(self._card_orcamento(o, com_menu=True))

    def menu_orcamento(self, caller, oid, numero):
        itens = [
            {"viewclass": "OneLineListItem", "text": "Abrir / Editar",
             "on_release": lambda: (self._fecha_menu(), self.abrir_orcamento(oid))},
            {"viewclass": "OneLineListItem", "text": "Gerar PDF",
             "on_release": lambda: (self._fecha_menu(), self.abrir_orcamento(oid, gerar=True))},
            {"viewclass": "OneLineListItem", "text": "Marcar como Aprovado",
             "on_release": lambda: (self._fecha_menu(), self._set_status(oid, "Aprovado"))},
            {"viewclass": "OneLineListItem", "text": "Marcar como Enviado",
             "on_release": lambda: (self._fecha_menu(), self._set_status(oid, "Enviado"))},
            {"viewclass": "OneLineListItem", "text": "Excluir",
             "on_release": lambda: (self._fecha_menu(), self.confirmar_excluir_orc(oid, numero))},
        ]
        self._menu = MDDropdownMenu(caller=caller, items=itens, width_mult=4)
        self._menu.open()

    def _fecha_menu(self):
        if self._menu:
            self._menu.dismiss()

    def _set_status(self, oid, status):
        self.db.atualizar_status(oid, status)
        self.refresh_orcamentos()
        self.toast(f"Status: {status}")

    def confirmar_excluir_orc(self, oid, numero):
        self._dialog("Excluir orçamento", f"Excluir o orçamento {numero}? Esta ação não pode ser desfeita.",
                     on_ok=lambda: self._excluir_orc(oid), ok_text="Excluir")

    def _excluir_orc(self, oid):
        self.db.excluir_orcamento(oid)
        self.refresh_orcamentos()
        self.refresh_dashboard()
        self.toast("Orçamento excluído.")

    # =====================================================================
    # LISTA DE CLIENTES
    # =====================================================================
    def refresh_clientes(self):
        if "busca_cli" not in self.root.ids:
            return
        filtro = self.root.ids.busca_cli.text.strip()
        lista = self.root.ids.lista_cli
        lista.clear_widgets()
        lista.spacing = dp(8)
        lista.padding = [dp(4), dp(6), dp(4), dp(6)]
        clientes = self.db.listar_clientes(filtro)
        if not clientes:
            lista.add_widget(OneLineListItem(text="Nenhum cliente cadastrado."))
            return
        for c in clientes:
            lista.add_widget(self._card_cliente(c))

    def _card_cliente(self, c):
        card = MDCard(size_hint_y=None, height=dp(68), radius=[dp(16)], elevation=1,
                      padding=(dp(12), dp(8)), spacing=dp(10), ripple_behavior=True)
        card.bind(on_release=lambda w, cid=c["id"]: self.ver_orcamentos_cliente(cid))
        circ = MDCard(size_hint=(None, None), size=(dp(44), dp(44)), radius=[dp(22)],
                      md_bg_color=_cor_alpha(ACCENT_METRICAS[3], 0.16), elevation=0,
                      pos_hint={"center_y": .5})
        # inicial do nome
        inicial = (c["nome"].strip()[:1] or "?").upper()
        circ.add_widget(MDLabel(text=inicial, halign="center", bold=True,
                                theme_text_color="Custom", text_color=_cor(ACCENT_METRICAS[3])))
        card.add_widget(circ)
        meio = MDBoxLayout(orientation="vertical", pos_hint={"center_y": .5})
        meio.add_widget(MDLabel(text=c["nome"], bold=True, font_style="Subtitle1", shorten=True))
        meio.add_widget(MDLabel(
            text=(c.get("telefone") or c.get("email") or c.get("documento") or "—"),
            theme_text_color="Secondary", font_style="Caption", shorten=True))
        card.add_widget(meio)
        bt = MDIconButton(icon="dots-vertical", pos_hint={"center_y": .5})
        bt.bind(on_release=lambda w, cid=c["id"], nome=c["nome"]: self.menu_cliente(w, cid, nome))
        card.add_widget(bt)
        return card

    def menu_cliente(self, caller, cid, nome):
        itens = [
            {"viewclass": "OneLineListItem", "text": "Ver orçamentos",
             "on_release": lambda: (self._fecha_menu(), self.ver_orcamentos_cliente(cid))},
            {"viewclass": "OneLineListItem", "text": "Editar",
             "on_release": lambda: (self._fecha_menu(), self.editar_cliente(cid))},
            {"viewclass": "OneLineListItem", "text": "Novo orçamento p/ este cliente",
             "on_release": lambda: (self._fecha_menu(), self.novo_orcamento(cliente_id=cid))},
            {"viewclass": "OneLineListItem", "text": "Excluir",
             "on_release": lambda: (self._fecha_menu(), self.confirmar_excluir_cli(cid, nome))},
        ]
        self._menu = MDDropdownMenu(caller=caller, items=itens, width_mult=4)
        self._menu.open()

    def confirmar_excluir_cli(self, cid, nome):
        self._dialog("Excluir cliente", f"Excluir o cliente “{nome}”?",
                     on_ok=lambda: self._excluir_cli(cid), ok_text="Excluir")

    def _excluir_cli(self, cid):
        self.db.excluir_cliente(cid)
        self.refresh_clientes()
        self.refresh_dashboard()
        self.toast("Cliente excluído.")

    def ver_orcamentos_cliente(self, cid):
        cli = self.db.obter_cliente(cid)
        if not cli:
            return
        self.root.ids.appbar_vercli.title = cli["nome"]
        lista = self.root.ids.lista_vercli
        lista.clear_widgets()
        lista.add_widget(OneLineListItem(text="＋ Novo orçamento para este cliente",
                                         on_release=lambda x: self.novo_orcamento(cliente_id=cid)))
        orcs = self.db.orcamentos_do_cliente(cid)
        if not orcs:
            lista.add_widget(OneLineListItem(text="Nenhum orçamento para este cliente."))
        for o in orcs:
            lista.add_widget(TwoLineListItem(
                text=f"{o['numero']}  •  {fmt_moeda(o['total'])}",
                secondary_text=o.get("status", ""),
                on_release=lambda x, oid=o["id"]: self.abrir_orcamento(oid),
            ))
        self.root.current = "ver_cliente"

    # =====================================================================
    # FORMULÁRIO DE CLIENTE
    # =====================================================================
    def novo_cliente(self):
        self.cli_editando = None
        self._montar_form_cliente({})
        self.root.current = "form_cliente"

    def editar_cliente(self, cid):
        cli = self.db.obter_cliente(cid)
        self.cli_editando = cid
        self._montar_form_cliente(cli or {})
        self.root.current = "form_cliente"

    def _montar_form_cliente(self, cli):
        box = self.root.ids.form_cli_box
        box.clear_widgets()
        self._cli_fields = {}
        campos = [
            ("nome", "Nome / Razão social *", False),
            ("documento", "CPF / CNPJ", False),
            ("endereco", "Endereço", True),
            ("telefone", "Telefone", False),
            ("email", "E-mail", False),
        ]
        for chave, hint, multiline in campos:
            tf = make_field(hint, cli.get(chave) or "", multiline=multiline)
            self._cli_fields[chave] = tf
            box.add_widget(tf)
        box.add_widget(MDRaisedButton(text="Salvar cliente", icon="content-save",
                                      pos_hint={"center_x": .5},
                                      on_release=lambda x: self.salvar_cliente_form()))

    def salvar_cliente_form(self):
        dados = {k: v.text.strip() for k, v in self._cli_fields.items()}
        if not dados.get("nome"):
            self.toast("Informe o nome do cliente.")
            return
        if self.cli_editando:
            dados["id"] = self.cli_editando
        self.db.salvar_cliente(dados)
        self.toast("Cliente salvo.")
        self.voltar_main("tab_clientes")
        self.refresh_clientes()
        self.refresh_dashboard()

    # =====================================================================
    # FORMULÁRIO DE ORÇAMENTO
    # =====================================================================
    def novo_orcamento(self, cliente_id=None):
        self.orc_editando = None
        self.itens_atuais = []
        self.fotos_atuais = []
        self.desconto_tipo = "valor"
        emp = self.db.empresa()
        dados = {
            "numero": self.db.gerar_numero(),
            "empresa": dict(emp),
            "cliente": {},
            "termos": termos_padrao(),
            "ordem_servico": ordem_servico_padrao(),
            "desconto": {"tipo": "valor", "valor": 0},
        }
        if cliente_id:
            cli = self.db.obter_cliente(cliente_id)
            if cli:
                dados["cliente"] = cli
        self._montar_form_orcamento(dados, titulo="Novo Orçamento")
        self.root.current = "form_orcamento"

    def abrir_orcamento(self, oid, gerar=False):
        o = self.db.obter_orcamento(oid)
        if not o:
            return
        self.orc_editando = oid
        self.itens_atuais = list(o.get("itens", []))
        self.fotos_atuais = [f.get("path") for f in o.get("fotos", []) if f.get("path")]
        self.desconto_tipo = o.get("desconto", {}).get("tipo", "valor")
        emp = o.get("dados_empresa") or self.db.empresa()
        dados = {
            "numero": o["numero"],
            "empresa": dict(emp),
            "cliente": {
                "nome": o.get("cli_nome") or "",
                "documento": o.get("cli_doc") or "",
                "endereco": o.get("cli_end") or "",
                "telefone": o.get("cli_tel") or "",
                "email": o.get("cli_email") or "",
            },
            "termos": o.get("termos") or termos_padrao(),
            "ordem_servico": o.get("ordem_servico") or "",
            "desconto": o.get("desconto") or {"tipo": "valor", "valor": 0},
        }
        self._montar_form_orcamento(dados, titulo=o["numero"])
        self.root.current = "form_orcamento"
        if gerar:
            self.gerar_pdf_orcamento()

    def _montar_form_orcamento(self, dados, titulo="Orçamento"):
        self.root.ids.appbar_orc.title = titulo
        box = self.root.ids.form_orc_box
        box.clear_widgets()
        emp = dados["empresa"]
        cli = dados["cliente"]

        def secao(txt):
            box.add_widget(MDLabel(text=txt, font_style="Subtitle1", bold=True,
                                   adaptive_height=True, theme_text_color="Primary"))

        def campo(hint, valor, multiline=False):
            tf = make_field(hint, valor or "", multiline=multiline)
            box.add_widget(tf)
            return tf

        self._f_numero = campo("Número do orçamento", dados["numero"])

        secao("Dados da empresa")
        self._f_emp_nome = campo("Nome da empresa", emp.get("nome"))
        self._f_emp_cnpj = campo("CNPJ", emp.get("cnpj"))
        self._f_emp_end = campo("Endereço", emp.get("endereco"), multiline=True)
        self._f_emp_tel = campo("Telefone", emp.get("telefone"))
        self._f_emp_email = campo("E-mail", emp.get("email"))
        self._f_emp_sub = campo("Subtítulo (opcional)", emp.get("subtitulo"))
        self._logo_orc = emp.get("logo_path") or ""
        linha_logo = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(48))
        self._lbl_logo = MDLabel(text=self._nome_logo(self._logo_orc),
                                 theme_text_color="Secondary", adaptive_height=True)
        linha_logo.add_widget(MDRaisedButton(text="Logomarca", icon="image",
                                             on_release=lambda x: self._escolher_logo_orc()))
        linha_logo.add_widget(self._lbl_logo)
        box.add_widget(linha_logo)

        secao("Cliente")
        linha_cli = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(48))
        btn_sel = MDRaisedButton(text="Selecionar existente", icon="account-search")
        btn_sel.bind(on_release=lambda w: self._menu_selecionar_cliente(w))
        linha_cli.add_widget(btn_sel)
        box.add_widget(linha_cli)
        self._f_cli_nome = campo("Nome do cliente *", cli.get("nome"))
        self._f_cli_doc = campo("CPF / CNPJ", cli.get("documento"))
        self._f_cli_end = campo("Endereço", cli.get("endereco"), multiline=True)
        self._f_cli_tel = campo("Telefone", cli.get("telefone"))
        self._f_cli_email = campo("E-mail", cli.get("email"))

        secao("Itens")
        add_box = MDCard(orientation="vertical", padding=dp(10), spacing=dp(6),
                         radius=[dp(12)], size_hint_y=None, elevation=1)
        add_box.bind(minimum_height=add_box.setter("height"))
        self._f_item_desc = MDTextField(hint_text="Descrição do item", mode="rectangle")
        add_box.add_widget(self._f_item_desc)
        linha_item = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(48))
        self._f_item_qtd = make_field("Qtd", "1", input_filter="float", size_hint_x=.3)
        self._f_item_unid = make_field("Unid.", "un", size_hint_x=.3)
        self._f_item_unid.bind(focus=self._menu_unidade)
        self._f_item_valor = MDTextField(hint_text="Valor unit.", mode="rectangle",
                                         input_filter="float", size_hint_x=.4)
        linha_item.add_widget(self._f_item_qtd)
        linha_item.add_widget(self._f_item_unid)
        linha_item.add_widget(self._f_item_valor)
        add_box.add_widget(linha_item)
        add_box.add_widget(MDRaisedButton(text="Adicionar item", icon="plus",
                                          pos_hint={"center_x": .5},
                                          on_release=lambda x: self.add_item()))
        box.add_widget(add_box)

        self._itens_container = MDBoxLayout(orientation="vertical", adaptive_height=True,
                                            spacing=dp(2))
        box.add_widget(self._itens_container)

        secao("Desconto")
        linha_desc = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(56))
        self._f_desc_valor = make_field("Valor do desconto",
                                        dados["desconto"].get("valor", 0) or "",
                                        input_filter="float")
        self._f_desc_valor.bind(text=lambda *a: self._atualizar_total())
        self._btn_desc_tipo = MDRaisedButton(
            text="R$" if self.desconto_tipo == "valor" else "%",
            on_release=lambda x: self._toggle_desc_tipo())
        linha_desc.add_widget(self._f_desc_valor)
        linha_desc.add_widget(self._btn_desc_tipo)
        box.add_widget(linha_desc)

        self._lbl_total = MDLabel(text="TOTAL: R$ 0,00", font_style="H6", bold=True,
                                  adaptive_height=True, theme_text_color="Primary")
        box.add_widget(self._lbl_total)

        secao("Fotos (máx. 4)")
        linha_fotos = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(48))
        linha_fotos.add_widget(MDRaisedButton(text="Adicionar foto", icon="camera-plus",
                                              on_release=lambda x: self.add_foto()))
        self._lbl_fotos = MDLabel(text=self._texto_fotos(), theme_text_color="Secondary",
                                  adaptive_height=True)
        linha_fotos.add_widget(self._lbl_fotos)
        box.add_widget(linha_fotos)

        secao("Condições comerciais e prazos")
        self._f_termos = make_field("Termos e condições", dados["termos"], multiline=True)
        box.add_widget(self._f_termos)

        secao("Ordem de serviço (opcional)")
        self._f_os = make_field("Ordem de serviço", dados["ordem_servico"], multiline=True)
        box.add_widget(self._f_os)

        finais = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(60),
                             padding=[0, dp(8), 0, dp(16)])
        finais.add_widget(MDRaisedButton(text="Salvar", icon="content-save",
                                         on_release=lambda x: self.salvar_orcamento()))
        finais.add_widget(MDRaisedButton(text="Gerar PDF", icon="file-pdf-box",
                                         on_release=lambda x: self.gerar_pdf_orcamento()))
        box.add_widget(finais)

        self._render_itens()

    # ---- helpers do formulário de orçamento
    def _nome_logo(self, path):
        return os.path.basename(path) if path else "Nenhuma selecionada"

    def _texto_fotos(self):
        n = len(self.fotos_atuais)
        return f"{n} foto(s) selecionada(s)" if n else "Nenhuma foto"

    def _menu_unidade(self, field, focus):
        if not focus:
            return
        itens = [{"viewclass": "OneLineListItem", "text": u,
                  "on_release": lambda u=u: self._set_unidade(u)} for u in UNIDADES]
        self._menu = MDDropdownMenu(caller=field, items=itens, width_mult=3)
        self._menu.open()

    def _set_unidade(self, u):
        self._f_item_unid.text = u
        self._fecha_menu()

    def _menu_selecionar_cliente(self, caller):
        clientes = self.db.listar_clientes()
        if not clientes:
            self.toast("Nenhum cliente cadastrado ainda.")
            return
        itens = [{"viewclass": "OneLineListItem", "text": c["nome"],
                  "on_release": lambda c=c: self._preencher_cliente(c)} for c in clientes]
        self._menu = MDDropdownMenu(caller=caller, items=itens, width_mult=4)
        self._menu.open()

    def _preencher_cliente(self, c):
        self._f_cli_nome.text = c.get("nome") or ""
        self._f_cli_doc.text = c.get("documento") or ""
        self._f_cli_end.text = c.get("endereco") or ""
        self._f_cli_tel.text = c.get("telefone") or ""
        self._f_cli_email.text = c.get("email") or ""
        self._fecha_menu()

    def _toggle_desc_tipo(self):
        self.desconto_tipo = "percentual" if self.desconto_tipo == "valor" else "valor"
        self._btn_desc_tipo.text = "R$" if self.desconto_tipo == "valor" else "%"
        self._atualizar_total()

    def add_item(self):
        desc = self._f_item_desc.text.strip()
        valor = parse_num(self._f_item_valor.text)
        qtd = parse_num(self._f_item_qtd.text) or 1
        unid = self._f_item_unid.text.strip() or "un"
        if not desc or valor <= 0:
            self.toast("Preencha descrição e valor.")
            return
        self.itens_atuais.append({
            "descricao": desc, "quantidade": qtd, "unidade": unid,
            "valor_unitario": valor, "total": qtd * valor,
        })
        self._f_item_desc.text = ""
        self._f_item_valor.text = ""
        self._f_item_qtd.text = "1"
        self._render_itens()

    def _render_itens(self):
        cont = self._itens_container
        cont.clear_widgets()
        if not self.itens_atuais:
            cont.add_widget(MDLabel(text="Nenhum item adicionado.",
                                    theme_text_color="Secondary", adaptive_height=True))
        for idx, it in enumerate(self.itens_atuais):
            qtd = it["quantidade"]
            qtd_fmt = int(qtd) if float(qtd).is_integer() else qtd
            item = TwoLineAvatarIconListItem(
                text=it["descricao"],
                secondary_text=f"{qtd_fmt} {it['unidade']} × {fmt_moeda(it['valor_unitario'])} = {fmt_moeda(it['total'])}",
                on_release=lambda x, i=idx: self._editar_item(i),
            )
            item.add_widget(IconLeftWidget(icon="wrench-outline"))
            rem = IconRightWidget(icon="trash-can-outline")
            rem.bind(on_release=lambda w, i=idx: self._remover_item(i))
            item.add_widget(rem)
            cont.add_widget(item)
        self._atualizar_total()

    def _remover_item(self, idx):
        if 0 <= idx < len(self.itens_atuais):
            self.itens_atuais.pop(idx)
        self._render_itens()

    def _editar_item(self, idx):
        it = self.itens_atuais[idx]
        cont = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(8),
                           size_hint_y=None, height=dp(250), padding=dp(4))
        f_desc = make_field("Descrição", it["descricao"])
        f_qtd = make_field("Qtd", it["quantidade"], input_filter="float")
        f_unid = make_field("Unidade", it["unidade"])
        f_valor = make_field("Valor unit.", it["valor_unitario"], input_filter="float")
        for w in (f_desc, f_qtd, f_unid, f_valor):
            cont.add_widget(w)

        def salvar(*_):
            q = parse_num(f_qtd.text) or 1
            v = parse_num(f_valor.text)
            self.itens_atuais[idx] = {
                "descricao": f_desc.text.strip(), "quantidade": q,
                "unidade": f_unid.text.strip() or "un", "valor_unitario": v, "total": q * v,
            }
            self._d.dismiss()
            self._render_itens()

        self._d = MDDialog(
            title="Editar item", type="custom", content_cls=cont,
            buttons=[MDFlatButton(text="Cancelar", on_release=lambda x: self._d.dismiss()),
                     MDRaisedButton(text="Salvar", on_release=salvar)],
        )
        self._d.open()

    def _calcular_totais(self):
        bruto = sum(i["total"] for i in self.itens_atuais)
        dval = parse_num(self._f_desc_valor.text)
        desc = bruto * (dval / 100) if self.desconto_tipo == "percentual" else dval
        desc = min(max(desc, 0), bruto)
        return bruto, dval, desc, max(bruto - desc, 0)

    def _atualizar_total(self):
        if not hasattr(self, "_lbl_total"):
            return
        _, _, _, total = self._calcular_totais()
        self._lbl_total.text = f"TOTAL: {fmt_moeda(total)}"

    def add_foto(self):
        if len(self.fotos_atuais) >= 4:
            self.toast("Máximo de 4 fotos.")
            return
        escolher_imagem(self._foto_selecionada, prefixo="foto")

    def _foto_selecionada(self, caminho):
        if caminho:
            self.fotos_atuais.append(caminho)
            self._lbl_fotos.text = self._texto_fotos()
            self.toast("Foto adicionada.")

    def _escolher_logo_orc(self):
        escolher_imagem(self._logo_orc_selecionada, prefixo="logo")

    def _logo_orc_selecionada(self, caminho):
        if caminho:
            self._logo_orc = caminho
            self._lbl_logo.text = self._nome_logo(self._logo_orc)

    def _coletar_orcamento(self):
        bruto, dval, desc, total = self._calcular_totais()
        return {
            "id": self.orc_editando,
            "numero": self._f_numero.text.strip(),
            "empresa": {
                "nome": self._f_emp_nome.text.strip(),
                "cnpj": self._f_emp_cnpj.text.strip(),
                "endereco": self._f_emp_end.text.strip(),
                "telefone": self._f_emp_tel.text.strip(),
                "email": self._f_emp_email.text.strip(),
                "subtitulo": self._f_emp_sub.text.strip(),
                "logo_path": self._logo_orc,
            },
            "cliente": {
                "nome": self._f_cli_nome.text.strip(),
                "documento": self._f_cli_doc.text.strip(),
                "endereco": self._f_cli_end.text.strip(),
                "telefone": self._f_cli_tel.text.strip(),
                "email": self._f_cli_email.text.strip(),
            },
            "itens": self.itens_atuais,
            "termos": self._f_termos.text.strip(),
            "ordem_servico": self._f_os.text.strip(),
            "desconto": {"tipo": self.desconto_tipo, "valor": dval},
            "fotos": [{"path": p} for p in self.fotos_atuais],
            "total": total,
            "total_bruto": bruto,
            "desconto_calculado": desc,
            "status": "Rascunho",
        }

    def salvar_orcamento(self, silencioso=False):
        try:
            dados = self._coletar_orcamento()
        except Exception as e:
            self._dialog("Erro", f"Não foi possível ler os dados do formulário:\n{e}",
                         cancel=False)
            return False
        if not dados["cliente"]["nome"]:
            self.toast("Informe o nome do cliente.")
            return False
        if not dados["itens"]:
            self.toast("Adicione pelo menos um item.")
            return False
        novo = self.orc_editando is None
        try:
            oid = self.db.salvar_orcamento(dados)
        except Exception as e:
            self._dialog("Erro ao salvar", f"O orçamento não pôde ser salvo:\n{e}",
                         cancel=False)
            return False
        self.orc_editando = oid
        # Confirma que gravou de fato lendo de volta o número
        salvo = self.db.obter_orcamento(oid) or {}
        numero = salvo.get("numero") or dados.get("numero") or ""
        if self._f_numero.text.strip() != numero:
            self._f_numero.text = numero
        self.root.ids.appbar_orc.title = numero or "Orçamento"
        self.refresh_orcamentos()
        self.refresh_dashboard()
        if not silencioso:
            self._confirmar_salvo(oid, numero, novo)
        return True

    def _confirmar_salvo(self, oid, numero, novo):
        titulo = "Orçamento salvo!" if novo else "Orçamento atualizado!"
        botoes = [
            MDFlatButton(text="Continuar", on_release=lambda x: self._d.dismiss()),
            MDFlatButton(text="Ver na lista",
                         on_release=lambda x: (self._d.dismiss(), self._ver_lista_orcamentos())),
            MDRaisedButton(text="Gerar PDF",
                           on_release=lambda x: (self._d.dismiss(), self.gerar_pdf_orcamento())),
        ]
        self._d = MDDialog(
            title=titulo,
            text=f"Nº {numero} gravado com sucesso.\nJá aparece na aba Orçamentos.",
            buttons=botoes,
        )
        self._d.open()

    def _ver_lista_orcamentos(self):
        # limpa a busca para o novo item não ficar escondido por um filtro antigo
        if "busca_orc" in self.root.ids:
            self.root.ids.busca_orc.text = ""
        self.voltar_main("tab_orcamentos")
        self.refresh_orcamentos()

    def gerar_pdf_orcamento(self):
        if not self.salvar_orcamento(silencioso=True):
            return
        dados = self._coletar_orcamento()
        cfg = self.db.config()
        emp = dados["empresa"]
        d_pdf = {
            "numero": dados["numero"],
            "empresa": emp,
            "cliente": dados["cliente"],
            "itens": dados["itens"],
            "total_bruto": dados["total_bruto"],
            "desconto_valor": dados["desconto"]["valor"],
            "desconto_tipo": dados["desconto"]["tipo"],
            "desconto_calculado": dados["desconto_calculado"],
            "total_final": dados["total"],
            "termos": dados["termos"],
            "ordem_servico": dados["ordem_servico"],
            "fotos": [p for p in self.fotos_atuais],
        }
        nome = (dados["numero"] or "ORC").replace("/", "-") + ".pdf"
        caminho = os.path.join(shared_dir(), nome)
        try:
            gerar_pdf(caminho, d_pdf,
                      cor_primaria_hex=PALETAS.get(cfg.get("paleta", "Indigo"), "#4C6FD0"),
                      incluir_fotos=cfg.get("incluir_fotos_pdf", True))
        except Exception as e:
            self._dialog("Erro ao gerar PDF", str(e), cancel=False)
            return
        self._dialog(
            "PDF gerado com sucesso!",
            "Toque em Enviar para compartilhar (WhatsApp, Drive, e-mail...). "
            "Uma cópia também fica na pasta Downloads/OrcamentosJM do celular.",
            on_ok=lambda: self._compartilhar_pdf(caminho), ok_text="Enviar")

    def _compartilhar_pdf(self, caminho):
        if is_android():
            backup_mod.compartilhar_arquivo(caminho, mime="application/pdf")
        else:
            self._abrir_desktop(caminho)

    def _abrir_desktop(self, caminho):
        import subprocess
        import sys
        try:
            if sys.platform.startswith("win"):
                os.startfile(caminho)  # noqa
            elif sys.platform == "darwin":
                subprocess.Popen(["open", caminho])
            else:
                subprocess.Popen(["xdg-open", caminho])
        except Exception:
            self.toast(f"Arquivo: {caminho}")

    # =====================================================================
    # CONFIGURAÇÕES
    # =====================================================================
    def montar_config(self):
        box = self.root.ids.config_box
        box.clear_widgets()
        emp = self.db.empresa()
        cfg = self.db.config()

        box.add_widget(MDLabel(text="Perfil da empresa", font_style="H6", bold=True,
                               adaptive_height=True))
        box.add_widget(MDLabel(text="Estes dados aparecem por padrão em novos orçamentos e no PDF.",
                               theme_text_color="Secondary", adaptive_height=True))
        self._c_nome = make_field("Nome da empresa", emp.get("nome") or "")
        self._c_cnpj = make_field("CNPJ", emp.get("cnpj") or "")
        self._c_end = make_field("Endereço", emp.get("endereco") or "", multiline=True)
        self._c_tel = make_field("Telefone", emp.get("telefone") or "")
        self._c_email = make_field("E-mail", emp.get("email") or "")
        self._c_sub = make_field("Subtítulo (opcional)", emp.get("subtitulo") or "")
        for w in (self._c_nome, self._c_cnpj, self._c_end, self._c_tel, self._c_email, self._c_sub):
            box.add_widget(w)

        self._c_logo = emp.get("logo_path") or ""
        linha_logo = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(48))
        self._c_lbl_logo = MDLabel(text=self._nome_logo(self._c_logo),
                                   theme_text_color="Secondary", adaptive_height=True)
        linha_logo.add_widget(MDRaisedButton(text="Escolher logomarca", icon="image",
                                             on_release=lambda x: self._escolher_logo_config()))
        linha_logo.add_widget(self._c_lbl_logo)
        box.add_widget(linha_logo)

        box.add_widget(MDLabel(text="Aparência", font_style="H6", bold=True, adaptive_height=True))
        from kivymd.uix.selectioncontrol import MDSwitch
        linha_tema = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(48))
        linha_tema.add_widget(MDLabel(text="Tema escuro", adaptive_height=True))
        self._c_switch_tema = MDSwitch(active=(cfg.get("tema") == "Dark"))
        self._c_switch_tema.bind(active=lambda w, v: self._set_tema(v))
        linha_tema.add_widget(self._c_switch_tema)
        box.add_widget(linha_tema)

        box.add_widget(MDLabel(text="Cor principal", font_style="Subtitle1", bold=True,
                               adaptive_height=True))
        grid_cores = MDBoxLayout(spacing=dp(6), size_hint_x=None, padding=[dp(2), 0])
        grid_cores.bind(minimum_width=grid_cores.setter("width"))
        for nome, hexcor in PALETAS.items():
            chip = MDCard(size_hint=(None, None), size=(dp(40), dp(40)), radius=[dp(20)],
                          md_bg_color=get_color_from_hex(hexcor), elevation=2)
            chip.bind(on_release=lambda w, n=nome: self._set_paleta(n))
            grid_cores.add_widget(chip)
        from kivy.uix.scrollview import ScrollView
        sv = ScrollView(size_hint_y=None, height=dp(52), do_scroll_y=False)
        sv.add_widget(grid_cores)
        box.add_widget(sv)

        linha_fotos = MDBoxLayout(adaptive_height=True, spacing=dp(8), size_hint_y=None, height=dp(48))
        linha_fotos.add_widget(MDLabel(text="Incluir fotos no PDF", adaptive_height=True))
        self._c_switch_fotos = MDSwitch(active=cfg.get("incluir_fotos_pdf", True))
        linha_fotos.add_widget(self._c_switch_fotos)
        box.add_widget(linha_fotos)

        box.add_widget(MDRaisedButton(text="Salvar configurações", icon="content-save",
                                      pos_hint={"center_x": .5},
                                      on_release=lambda x: self.salvar_config_form()))
        box.add_widget(MDFlatButton(text="Ajuda / Sobre o app",
                                    on_release=lambda x: self.mostrar_ajuda()))

    def _set_tema(self, dark):
        self.theme_cls.theme_style = "Dark" if dark else "Light"
        self.on_theme_change()

    def _set_paleta(self, nome):
        self.theme_cls.primary_palette = nome
        self.toast(f"Cor: {nome}")

    def _escolher_logo_config(self):
        escolher_imagem(self._logo_config_selecionada, prefixo="logo")

    def _logo_config_selecionada(self, caminho):
        if caminho:
            self._c_logo = caminho
            self._c_lbl_logo.text = self._nome_logo(self._c_logo)

    def salvar_config_form(self):
        self.db.salvar_empresa({
            "nome": self._c_nome.text.strip(),
            "cnpj": self._c_cnpj.text.strip(),
            "endereco": self._c_end.text.strip(),
            "telefone": self._c_tel.text.strip(),
            "email": self._c_email.text.strip(),
            "subtitulo": self._c_sub.text.strip(),
            "logo_path": self._c_logo,
        })
        self.db.salvar_config({
            "tema": self.theme_cls.theme_style,
            "paleta": self.theme_cls.primary_palette,
            "incluir_fotos_pdf": self._c_switch_fotos.active,
        })
        self.toast("Configurações salvas.")
        self.refresh_dashboard()

    # =====================================================================
    # BACKUP
    # =====================================================================
    def tela_backup(self):
        box = self.root.ids.backup_box
        box.clear_widgets()
        box.add_widget(MDLabel(text="Backup na nuvem", font_style="H6", bold=True,
                               adaptive_height=True))
        box.add_widget(MDLabel(
            text=("Gere um arquivo de backup com todos os clientes, orçamentos e "
                  "configurações. Ao compartilhar, escolha [b]Salvar no Drive[/b] "
                  "para enviar ao Google Drive — ou envie por e-mail/WhatsApp."),
            markup=True, theme_text_color="Secondary", adaptive_height=True))
        box.add_widget(MDRaisedButton(text="Gerar e enviar backup", icon="cloud-upload",
                                      pos_hint={"center_x": .5},
                                      on_release=lambda x: self.fazer_backup()))
        box.add_widget(MDRaisedButton(text="Restaurar backup", icon="backup-restore",
                                      pos_hint={"center_x": .5},
                                      on_release=lambda x: self.menu_restaurar(x)))
        self._lbl_backup = MDLabel(text="", theme_text_color="Secondary", adaptive_height=True)
        box.add_widget(self._lbl_backup)
        self.root.current = "backup"

    def fazer_backup(self):
        try:
            caminho = backup_mod.exportar_backup(self.db)
        except Exception as e:
            self._dialog("Erro no backup", str(e), cancel=False)
            return
        self._lbl_backup.text = f"Backup salvo em:\n{caminho}"
        if is_android():
            backup_mod.compartilhar_arquivo(caminho)
        else:
            self.toast("Backup gerado (desktop).")

    def menu_restaurar(self, caller):
        """Mostra os backups que o próprio app salvou (restauração garantida) e
        também a opção de escolher um arquivo de outro local."""
        import glob
        backups = sorted(glob.glob(os.path.join(shared_dir(), "backup_*.json")),
                         reverse=True)
        itens = []
        for b in backups:
            rotulo = os.path.basename(b).replace("backup_orcamentos_", "").replace(".json", "")
            # formata AAAAMMDD_HHMMSS -> DD/MM/AAAA HH:MM
            legivel = rotulo
            try:
                d = rotulo.split("_")
                if len(d) == 2 and len(d[0]) == 8:
                    legivel = f"{d[0][6:8]}/{d[0][4:6]}/{d[0][0:4]} {d[1][0:2]}:{d[1][2:4]}"
            except Exception:
                pass
            itens.append({"viewclass": "OneLineListItem", "text": f"Backup de {legivel}",
                          "on_release": (lambda b=b: (self._fecha_menu(),
                                                      self._confirmar_restaurar(b)))})
        itens.append({"viewclass": "OneLineListItem", "text": "Escolher arquivo de outro local...",
                      "on_release": lambda: (self._fecha_menu(), self._restaurar_via_picker())})
        self._menu = MDDropdownMenu(caller=caller, items=itens, width_mult=5)
        self._menu.open()

    def _restaurar_via_picker(self):
        escolher_arquivo(self._restaurar_selecionado, prefixo="backup", ext_padrao=".json")

    def _restaurar_selecionado(self, caminho):
        if not caminho:
            from androidpicker import ultimo_erro
            motivo = ultimo_erro() or "Não foi possível ler o backup escolhido."
            self._dialog(
                "Não consegui abrir o arquivo",
                motivo + "\n\nDica: use a lista de backups do próprio app, ou salve o "
                ".json em Downloads e escolha-o pelo app \"Arquivos\".",
                cancel=False)
            return
        self._confirmar_restaurar(caminho)

    def _confirmar_restaurar(self, caminho):
        if not os.path.exists(caminho):
            self._dialog("Arquivo não encontrado", str(caminho), cancel=False)
            return

        def _do():
            try:
                r = backup_mod.restaurar_backup(self.db, caminho)
            except Exception as e:
                self._dialog("Erro ao restaurar", str(e), cancel=False)
                return
            self.refresh_dashboard()
            self.refresh_orcamentos()
            self.refresh_clientes()
            self._dialog("Backup restaurado",
                         f"{r['clientes']} cliente(s) e {r['orcamentos']} orçamento(s) restaurados.",
                         cancel=False)
        self._dialog("Restaurar backup",
                     "Isto substituirá os dados atuais. Deseja continuar?",
                     on_ok=_do, ok_text="Restaurar")

    # =====================================================================
    # AJUDA
    # =====================================================================
    def mostrar_ajuda(self):
        texto = (
            "• Novo orçamento: preencha empresa e cliente, adicione itens, ajuste "
            "desconto, termos e (opcional) a ordem de serviço, salve e gere o PDF.\n\n"
            "• Clientes: cadastre uma vez e reaproveite nos orçamentos.\n\n"
            "• Personalização: em Configurações, defina nome/logo/dados da empresa, "
            "tema e cor. Esses dados alimentam automaticamente o PDF.\n\n"
            "• Backup na nuvem: gere o backup e escolha “Salvar no Drive”.\n\n"
            "• Toque em um item da lista para editar; use o menu (⋮) para mais ações.")
        self._dialog("Como usar o app", texto, cancel=False)


if __name__ == "__main__":
    try:
        OrcamentosApp().run()
    except Exception:
        registrar_crash(traceback.format_exc())
        raise
