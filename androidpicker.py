"""Seletor de imagens robusto.

No Android, o seletor devolve um endereço ``content://`` que o app não consegue
ler diretamente depois (armazenamento com escopo). Por isso, ao escolher a
imagem, copiamos o conteúdo para a pasta interna do app e devolvemos esse caminho
local — assim a logomarca e as fotos sempre podem ser lidas ao gerar o PDF.
No desktop, usa o seletor do plyer normalmente.
"""
import os

from paths import is_android, data_dir


def _imagens_dir():
    d = os.path.join(data_dir(), "imagens")
    os.makedirs(d, exist_ok=True)
    return d


def _copiar_uri_para_interno(activity, uri, prefixo="img"):
    from jnius import autoclass
    resolver = activity.getContentResolver()
    mime = None
    try:
        mime = resolver.getType(uri)
    except Exception:
        pass
    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
           "image/webp": ".webp"}.get(mime, ".jpg")
    nome = f"{prefixo}_{abs(hash(uri.toString())) % (10 ** 9)}{ext}"
    destino = os.path.join(_imagens_dir(), nome)

    inp = resolver.openInputStream(uri)
    FileOutputStream = autoclass("java.io.FileOutputStream")
    out = FileOutputStream(destino)
    try:
        try:
            FileUtils = autoclass("android.os.FileUtils")  # API 29+
            FileUtils.copy(inp, out)
        except Exception:
            # fallback lento (Android antigo): copia byte a byte
            b = inp.read()
            while b != -1:
                out.write(b)
                b = inp.read()
    finally:
        try:
            out.flush()
            out.close()
        except Exception:
            pass
        try:
            inp.close()
        except Exception:
            pass
    return destino


def escolher_imagem(callback, prefixo="img"):
    """Abre o seletor de imagens e chama ``callback(caminho_local_ou_None)``."""
    if not is_android():
        try:
            from plyer import filechooser
            filechooser.open_file(
                on_selection=lambda sel: callback(sel[0] if sel else None),
                filters=[["Imagens", "*.png", "*.jpg", "*.jpeg"]])
        except Exception as e:
            print("filechooser desktop falhou:", e)
            callback(None)
        return

    from jnius import autoclass
    from android import activity as a_activity
    from kivy.clock import Clock

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    activity = PythonActivity.mActivity
    REQ = 0x9A71

    def _on_result(request, result, intent):
        if request != REQ:
            return
        try:
            a_activity.unbind(on_activity_result=_on_result)
        except Exception:
            pass
        caminho = None
        try:
            if intent is not None:
                uri = intent.getData()
                if uri is not None:
                    caminho = _copiar_uri_para_interno(activity, uri, prefixo)
        except Exception as e:
            print("erro ao importar imagem:", e)
        Clock.schedule_once(lambda dt: callback(caminho), 0)

    a_activity.bind(on_activity_result=_on_result)
    try:
        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("image/*")
        activity.startActivityForResult(intent, REQ)
    except Exception as e:
        print("erro ao abrir seletor:", e)
        try:
            a_activity.unbind(on_activity_result=_on_result)
        except Exception:
            pass
        callback(None)
