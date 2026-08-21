"""Seletor de imagens robusto.

No Android, o seletor devolve um endereço ``content://`` que o app não consegue
ler diretamente depois (armazenamento com escopo). Por isso, ao escolher a
imagem, copiamos o conteúdo para a pasta interna do app e devolvemos esse caminho
local — assim a logomarca e as fotos sempre podem ser lidas ao gerar o PDF.
No desktop, usa o seletor do plyer normalmente.
"""
import os

from paths import is_android, data_dir

# guarda o motivo da última falha do seletor, para mostrar ao usuário
_ULTIMO_ERRO = ""


def ultimo_erro():
    return _ULTIMO_ERRO


def _imagens_dir():
    d = os.path.join(data_dir(), "imagens")
    os.makedirs(d, exist_ok=True)
    return d


def _copiar_uri_para_interno(activity, uri, prefixo="img", ext_padrao=".jpg"):
    from jnius import autoclass
    resolver = activity.getContentResolver()
    mime = None
    try:
        mime = resolver.getType(uri)
    except Exception:
        pass
    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
           "image/webp": ".webp", "application/json": ".json",
           "text/plain": ".json"}.get(mime, ext_padrao)
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


def _escolher(callback, mime, tipo_plyer, prefixo, ext_padrao):
    """Núcleo do seletor: abre o seletor do sistema e devolve um caminho local
    legível (copiando o content:// para a pasta interna no Android)."""
    if not is_android():
        try:
            from plyer import filechooser
            filechooser.open_file(
                on_selection=lambda sel: callback(sel[0] if sel else None),
                filters=[tipo_plyer])
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
        global _ULTIMO_ERRO
        if request != REQ:
            return
        try:
            a_activity.unbind(on_activity_result=_on_result)
        except Exception:
            pass
        caminho = None
        _ULTIMO_ERRO = ""
        try:
            uri = None
            if intent is not None:
                uri = intent.getData()
                if uri is None:
                    try:
                        clip = intent.getClipData()
                        if clip is not None and clip.getItemCount() > 0:
                            uri = clip.getItemAt(0).getUri()
                    except Exception:
                        pass
            if uri is None:
                _ULTIMO_ERRO = "Nenhum arquivo foi retornado pelo seletor."
            else:
                caminho = _copiar_uri_para_interno(activity, uri, prefixo, ext_padrao)
                if not caminho or not os.path.exists(caminho) or os.path.getsize(caminho) == 0:
                    _ULTIMO_ERRO = "O arquivo escolhido não pôde ser lido/copiado."
                    caminho = None
        except Exception as e:
            import traceback
            _ULTIMO_ERRO = "".join(
                traceback.format_exception_only(type(e), e)).strip()
            caminho = None
        Clock.schedule_once(lambda dt: callback(caminho), 0)

    a_activity.bind(on_activity_result=_on_result)
    try:
        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType(mime)
        activity.startActivityForResult(intent, REQ)
    except Exception as e:
        global _ULTIMO_ERRO
        _ULTIMO_ERRO = "Não foi possível abrir o seletor: " + str(e)
        try:
            a_activity.unbind(on_activity_result=_on_result)
        except Exception:
            pass
        callback(None)


def escolher_imagem(callback, prefixo="img"):
    """Seletor de imagens. Chama ``callback(caminho_local_ou_None)``."""
    _escolher(callback, "image/*", ["Imagens", "*.png", "*.jpg", "*.jpeg"],
              prefixo, ".jpg")


def escolher_arquivo(callback, prefixo="arq", ext_padrao=".json"):
    """Seletor de arquivo genérico (ex.: backup .json). Devolve caminho local."""
    _escolher(callback, "*/*", ["Arquivos", "*.json"], prefixo, ext_padrao)
