"""Backup e restauração dos dados.

- ``exportar_backup`` gera um arquivo .json com clientes, orçamentos, perfil da
  empresa e configurações, salvo na pasta pública (Downloads/OrcamentosJM no
  Android).
- ``compartilhar_arquivo`` abre a folha de compartilhamento do Android
  (ACTION_SEND), onde o usuário escolhe **Salvar no Drive**, e-mail, WhatsApp,
  etc. — assim o backup vai para o Google Drive sem exigir login/OAuth no app.
- ``restaurar_backup`` recria os dados a partir de um arquivo .json.
"""
import json
import os
from datetime import datetime

from paths import shared_dir, is_android


def exportar_backup(db) -> str:
    """Serializa todos os dados num arquivo JSON e devolve o caminho."""
    db.cur.execute("SELECT * FROM clientes")
    clientes = [dict(r) for r in db.cur.fetchall()]
    db.cur.execute("SELECT * FROM orcamentos")
    orcamentos = [dict(r) for r in db.cur.fetchall()]

    payload = {
        "app": "OrcamentosJM",
        "versao_backup": 1,
        "gerado_em": datetime.now().isoformat(),
        "empresa": db.empresa(),
        "config": db.config(),
        "clientes": clientes,
        "orcamentos": orcamentos,
    }

    nome = f"backup_orcamentos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    caminho = os.path.join(shared_dir(), nome)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return caminho


def restaurar_backup(db, caminho) -> dict:
    """Restaura os dados do arquivo. Substitui clientes e orçamentos atuais.
    Devolve um resumo {clientes, orcamentos}."""
    with open(caminho, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if payload.get("app") != "OrcamentosJM":
        raise ValueError("Arquivo de backup inválido.")

    db.cur.execute("DELETE FROM orcamentos")
    db.cur.execute("DELETE FROM clientes")

    for c in payload.get("clientes", []):
        db.cur.execute(
            "INSERT INTO clientes (id, nome, documento, endereco, telefone, email, data_criacao) "
            "VALUES (?,?,?,?,?,?,?)",
            (c.get("id"), c.get("nome"), c.get("documento"), c.get("endereco"),
             c.get("telefone"), c.get("email"), c.get("data_criacao")),
        )
    for o in payload.get("orcamentos", []):
        db.cur.execute(
            """INSERT INTO orcamentos (id, numero, id_cliente, dados_empresa, itens, termos,
                   total, desconto, fotos, ordem_servico, data_criacao, data_validade, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (o.get("id"), o.get("numero"), o.get("id_cliente"), o.get("dados_empresa"),
             o.get("itens"), o.get("termos"), o.get("total"), o.get("desconto"),
             o.get("fotos"), o.get("ordem_servico"), o.get("data_criacao"),
             o.get("data_validade"), o.get("status")),
        )
    if payload.get("empresa"):
        db.set_config("empresa", payload["empresa"])
    if payload.get("config"):
        db.set_config("config", payload["config"])
    db.conn.commit()
    return {
        "clientes": len(payload.get("clientes", [])),
        "orcamentos": len(payload.get("orcamentos", [])),
    }


def compartilhar_arquivo(caminho, mime="application/json"):
    """Abre a folha de compartilhamento do Android para enviar o arquivo
    (Google Drive, e-mail, WhatsApp...). Sem efeito no desktop.

    Usa FileProvider quando disponível; caso contrário, desliga a checagem de
    StrictMode e usa uma URI file:// (compatível com apps sideloaded)."""
    if not is_android():
        return False
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        String = autoclass("java.lang.String")
        VERSION = autoclass("android.os.Build$VERSION")

        activity = PythonActivity.mActivity
        arquivo = File(caminho)

        uri = None
        # 1) MediaStore (Android 10+/API 29+): copia para a pasta pública Downloads
        #    e devolve uma URI content:// que OUTROS apps conseguem ler
        #    (WhatsApp, Drive, e-mail). É a forma que funciona sem FileProvider.
        if VERSION.SDK_INT >= 29:
            try:
                uri = _inserir_no_mediastore(activity, caminho, mime)
            except Exception as e:
                print("MediaStore falhou:", e)
                uri = None
        # 2) Fallback: FileProvider (se algum dia estiver configurado)
        if uri is None:
            try:
                FileProvider = autoclass("androidx.core.content.FileProvider")
                authority = activity.getPackageName() + ".fileprovider"
                uri = FileProvider.getUriForFile(activity, authority, arquivo)
            except Exception:
                uri = None
        # 3) Fallback: file:// com StrictMode desativado (Android antigo)
        if uri is None:
            try:
                StrictMode = autoclass("android.os.StrictMode")
                StrictMode.disableDeathOnFileUriExposure()
            except Exception:
                pass
            uri = Uri.fromFile(arquivo)

        intent = Intent(Intent.ACTION_SEND)
        intent.setType(mime)
        intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        chooser = Intent.createChooser(intent, cast("java.lang.CharSequence",
                                                    String("Enviar para...")))
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(chooser)
        return True
    except Exception as e:
        print("Falha ao compartilhar:", e)
        return False


def _inserir_no_mediastore(activity, caminho, mime):
    """Insere o arquivo na pasta pública Downloads/OrcamentosJM via MediaStore
    (API 29+) e devolve a URI content:// resultante (legível por outros apps)."""
    import os as _os
    from jnius import autoclass
    ContentValues = autoclass("android.content.ContentValues")
    MediaStoreDownloads = autoclass("android.provider.MediaStore$Downloads")
    resolver = activity.getContentResolver()

    nome = _os.path.basename(caminho)
    values = ContentValues()
    values.put("_display_name", nome)
    values.put("mime_type", mime or "application/octet-stream")
    values.put("relative_path", "Download/OrcamentosJM")
    uri = resolver.insert(MediaStoreDownloads.EXTERNAL_CONTENT_URI, values)
    if uri is None:
        return None
    out = resolver.openOutputStream(uri)
    try:
        with open(caminho, "rb") as f:
            dados = f.read()
        out.write(dados, 0, len(dados))
        out.flush()
    finally:
        out.close()
    return uri
