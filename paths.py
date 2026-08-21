"""Resolução de diretórios de dados que funciona no Android e no desktop.

No Android, o banco/config ficam no ``user_data_dir`` (privado, sempre gravável).
PDFs e backups vão para o diretório *externo* do app
(``getExternalFilesDir``) — sempre gravável sem permissão em qualquer versão do
Android e compartilhável para outros apps (Google Drive, e-mail, WhatsApp).
No desktop usamos pastas locais ao lado do código para facilitar os testes.
"""
import os
import sys


def is_android() -> bool:
    return "ANDROID_ARGUMENT" in os.environ or hasattr(sys, "getandroidapilevel")


def data_dir() -> str:
    """Diretório do banco/config (privado do app)."""
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None and getattr(app, "user_data_dir", None):
            base = app.user_data_dir
            os.makedirs(base, exist_ok=True)
            return base
    except Exception:
        pass
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_orcamentosjm")
    os.makedirs(base, exist_ok=True)
    return base


def shared_dir() -> str:
    """Diretório onde PDFs e backups são gerados.

    Usa sempre a pasta interna do app (``user_data_dir``), que é garantidamente
    gravável em qualquer versão do Android sem exigir permissão. O envio para
    outros apps e para a pasta pública Downloads é feito depois, via MediaStore
    (ver backup.compartilhar_arquivo)."""
    base = os.path.join(data_dir(), "arquivos")
    os.makedirs(base, exist_ok=True)
    return base
