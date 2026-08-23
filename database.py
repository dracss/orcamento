"""Camada de dados (SQLite) do app de Orçamentos.

Replica o esquema do sistema desktop original (clientes / orçamentos) e
acrescenta um perfil de empresa personalizável (nome, CNPJ, logo, cores) e a
numeração automática ORC-AAAA-NNN.
"""
import json
import os
import sqlite3
from datetime import datetime

from paths import data_dir


DEFAULTS_EMPRESA = {
    "nome": "",
    "cnpj": "",
    "endereco": "",
    "telefone": "",
    "email": "",
    "subtitulo": "",
    "logo_path": "",
}

DEFAULTS_CONFIG = {
    "cor_principal": "#4C6FD0",
    "cor_secundaria": "#F2A93B",
    "tema": "Light",          # Light | Dark
    "paleta": "Indigo",
    "incluir_fotos_pdf": True,
}


def termos_padrao() -> str:
    return (
        "1. FORMA DE PAGAMENTO: 50% no início do serviço e 50% ao término dos serviços executados.\n\n"
        "2. PRAZO DE EXECUÇÃO: Os serviços serão executados conforme cronograma a ser formalizado e acordado.\n\n"
        "3. VALIDADE DA PROPOSTA: Esta proposta tem validade para aceitação de 15 (quinze) dias, a contar de sua data de emissão.\n\n"
        "4. INÍCIO DOS SERVIÇOS: O início da execução ocorrerá em até 03 (três) dias úteis após a aprovação formal e assinatura do contrato ou ordem de serviço.\n\n"
        "5. OBSERVAÇÕES GERAIS:\n"
        "- Esta proposta foi elaborada com base nas informações e escopo de serviços fornecidos.\n"
        "- Quaisquer acréscimos, supressões ou modificações no escopo original sujeitarão o orçamento a revisão.\n"
        "- Todos os serviços serão executados por profissionais qualificados."
    )


def ordem_servico_padrao() -> str:
    return (
        "VALOR TOTAL ESTIMADO:\n"
        "A definir com base na medição final.\n"
        "Forma de Pagamento: 50% no início da execução dos serviços e 50% após conclusão e medição final.\n\n"
        "PRAZO DE EXECUÇÃO:\n"
        "Os serviços terão início em até 03 (três) dias úteis a partir da emissão desta ordem de serviço e serão concluídos conforme cronograma a ser acordado com a CONTRATANTE.\n\n"
        "RESPONSABILIDADES DAS PARTES:\n"
        "CONTRATADA:\n"
        "- Executar os serviços com qualidade e dentro do prazo estipulado.\n"
        "- Fornecer todos os materiais necessários para a execução dos serviços.\n"
        "- Garantir a mão de obra especializada e equipamentos adequados.\n"
        "- Responsabilizar-se por quaisquer danos causados por negligência ou imperícia.\n"
        "CONTRATANTE:\n"
        "- Permitir o acesso da CONTRATADA ao local de execução dos serviços.\n"
        "- Fornecer as condições necessárias para a execução dos serviços.\n"
        "- Preparação do local, incluindo limpeza, liberação da via, sinalização de segurança e destinação ambiental dos resíduos excedentes.\n"
        "- Pagar os valores combinados nos prazos acordados.\n"
        "- Responsabilizar-se por informações incorretas ou incompletas que possam prejudicar a execução dos serviços.\n\n"
        "ACEITE:\n"
        "Ao assinar abaixo, a CONTRATANTE declara estar de acordo com o escopo de serviços, valores e condições comerciais descritos, autorizando o início dos trabalhos.\n\n"
        "Eu, _______________________________________________, portador do CPF _____________________, declaro que li e concordo com todos os termos desta ordem de serviço.\n\n"
        "Data: ____/____/______      Assinatura: ______________________________________\n\n"
        "Representante da CONTRATADA: _________________________      Data: ____/____/______"
    )


class Database:
    def __init__(self):
        self.path = os.path.join(data_dir(), "orcamentosjm.db")
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cur = self.conn.cursor()
        self._init_db()

    # ------------------------------------------------------------------ schema
    def _init_db(self):
        self.cur.execute(
            """CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                documento TEXT,
                endereco TEXT,
                telefone TEXT,
                email TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self.cur.execute(
            """CREATE TABLE IF NOT EXISTS orcamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE,
                id_cliente INTEGER,
                dados_empresa TEXT,
                itens TEXT,
                termos TEXT,
                total REAL,
                desconto TEXT,
                fotos TEXT,
                ordem_servico TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_validade TIMESTAMP,
                status TEXT DEFAULT 'Rascunho',
                FOREIGN KEY (id_cliente) REFERENCES clientes (id)
            )"""
        )
        self.cur.execute(
            """CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )"""
        )
        self.conn.commit()

    # ------------------------------------------------------------- config store
    def get_config(self, chave, default=None):
        self.cur.execute("SELECT valor FROM configuracoes WHERE chave=?", (chave,))
        row = self.cur.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["valor"])
        except (json.JSONDecodeError, TypeError):
            return row["valor"]

    def set_config(self, chave, valor):
        self.cur.execute(
            "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, json.dumps(valor)),
        )
        self.conn.commit()

    def empresa(self) -> dict:
        dados = dict(DEFAULTS_EMPRESA)
        dados.update(self.get_config("empresa", {}) or {})
        return dados

    def salvar_empresa(self, dados: dict):
        atual = self.empresa()
        atual.update(dados)
        self.set_config("empresa", atual)

    def config(self) -> dict:
        dados = dict(DEFAULTS_CONFIG)
        dados.update(self.get_config("config", {}) or {})
        return dados

    def salvar_config(self, dados: dict):
        atual = self.config()
        atual.update(dados)
        self.set_config("config", atual)

    # ---------------------------------------------------------------- clientes
    def listar_clientes(self, filtro=""):
        if filtro:
            like = f"%{filtro}%"
            self.cur.execute(
                "SELECT * FROM clientes WHERE nome LIKE ? OR documento LIKE ? "
                "OR email LIKE ? ORDER BY nome",
                (like, like, like),
            )
        else:
            self.cur.execute("SELECT * FROM clientes ORDER BY nome")
        return [dict(r) for r in self.cur.fetchall()]

    def obter_cliente(self, cid):
        self.cur.execute("SELECT * FROM clientes WHERE id=?", (cid,))
        row = self.cur.fetchone()
        return dict(row) if row else None

    def obter_cliente_por_nome(self, nome):
        self.cur.execute("SELECT * FROM clientes WHERE nome=?", (nome,))
        row = self.cur.fetchone()
        return dict(row) if row else None

    def salvar_cliente(self, dados: dict):
        """Insere ou atualiza (por id se presente). Devolve o id."""
        if dados.get("id"):
            self.cur.execute(
                "UPDATE clientes SET nome=?, documento=?, endereco=?, telefone=?, email=? WHERE id=?",
                (dados["nome"], dados.get("documento", ""), dados.get("endereco", ""),
                 dados.get("telefone", ""), dados.get("email", ""), dados["id"]),
            )
            self.conn.commit()
            return dados["id"]
        # se já existe cliente com o mesmo nome, atualiza
        existente = self.obter_cliente_por_nome(dados["nome"])
        if existente:
            self.cur.execute(
                "UPDATE clientes SET documento=?, endereco=?, telefone=?, email=? WHERE id=?",
                (dados.get("documento", ""), dados.get("endereco", ""),
                 dados.get("telefone", ""), dados.get("email", ""), existente["id"]),
            )
            self.conn.commit()
            return existente["id"]
        self.cur.execute(
            "INSERT INTO clientes (nome, documento, endereco, telefone, email) VALUES (?,?,?,?,?)",
            (dados["nome"], dados.get("documento", ""), dados.get("endereco", ""),
             dados.get("telefone", ""), dados.get("email", "")),
        )
        self.conn.commit()
        return self.cur.lastrowid

    def excluir_cliente(self, cid):
        self.cur.execute("DELETE FROM clientes WHERE id=?", (cid,))
        self.conn.commit()

    # -------------------------------------------------------------- orçamentos
    def gerar_numero(self) -> str:
        ano = datetime.now().year
        self.cur.execute(
            "SELECT numero FROM orcamentos WHERE numero LIKE ? ORDER BY numero DESC LIMIT 1",
            (f"ORC-{ano}-%",),
        )
        row = self.cur.fetchone()
        seq = 1
        if row and row["numero"]:
            try:
                partes = row["numero"].split("-")
                if len(partes) == 3:
                    seq = int(partes[2]) + 1
            except (ValueError, IndexError):
                seq = 1
        for _ in range(1000):
            numero = f"ORC-{ano}-{seq:03d}"
            self.cur.execute("SELECT id FROM orcamentos WHERE numero=?", (numero,))
            if not self.cur.fetchone():
                return numero
            seq += 1
        return f"ORC-{ano}-{int(datetime.now().timestamp())}"

    def listar_orcamentos(self, filtro=""):
        sql = (
            "SELECT o.id, o.numero, o.total, o.status, o.data_criacao, "
            "c.nome AS cliente_nome FROM orcamentos o "
            "LEFT JOIN clientes c ON o.id_cliente=c.id "
        )
        params = ()
        if filtro:
            like = f"%{filtro}%"
            sql += "WHERE o.numero LIKE ? OR c.nome LIKE ? "
            params = (like, like)
        sql += "ORDER BY o.id DESC"
        self.cur.execute(sql, params)
        return [dict(r) for r in self.cur.fetchall()]

    def orcamentos_do_cliente(self, cid):
        self.cur.execute(
            "SELECT id, numero, total, status, data_criacao FROM orcamentos "
            "WHERE id_cliente=? ORDER BY id DESC",
            (cid,),
        )
        return [dict(r) for r in self.cur.fetchall()]

    def obter_orcamento(self, oid):
        self.cur.execute(
            """SELECT o.*, c.nome AS cli_nome, c.documento AS cli_doc,
                      c.endereco AS cli_end, c.telefone AS cli_tel, c.email AS cli_email
               FROM orcamentos o LEFT JOIN clientes c ON o.id_cliente=c.id
               WHERE o.id=?""",
            (oid,),
        )
        row = self.cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["dados_empresa"] = json.loads(d["dados_empresa"]) if d.get("dados_empresa") else {}
        d["itens"] = json.loads(d["itens"]) if d.get("itens") else []
        d["desconto"] = json.loads(d["desconto"]) if d.get("desconto") else {"tipo": "valor", "valor": 0}
        d["fotos"] = json.loads(d["fotos"]) if d.get("fotos") else []
        return d

    def salvar_orcamento(self, dados: dict) -> int:
        """Insere ou atualiza (por dados['id']). Devolve o id do orçamento."""
        cliente = dados["cliente"]
        cliente_id = self.salvar_cliente(cliente)

        dados_empresa = json.dumps(dados["empresa"])
        itens_json = json.dumps(dados["itens"])
        desconto_json = json.dumps(dados["desconto"])
        fotos_json = json.dumps(dados.get("fotos", []))

        if dados.get("id"):
            self.cur.execute(
                """UPDATE orcamentos SET numero=?, id_cliente=?, dados_empresa=?, itens=?,
                       termos=?, total=?, desconto=?, fotos=?, ordem_servico=?, status=?
                   WHERE id=?""",
                (dados["numero"], cliente_id, dados_empresa, itens_json, dados["termos"],
                 dados["total"], desconto_json, fotos_json, dados["ordem_servico"],
                 dados.get("status", "Rascunho"), dados["id"]),
            )
            self.conn.commit()
            return dados["id"]

        numero = dados.get("numero") or self.gerar_numero()
        self.cur.execute(
            """INSERT INTO orcamentos (numero, id_cliente, dados_empresa, itens, termos,
                   total, desconto, fotos, ordem_servico, status)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (numero, cliente_id, dados_empresa, itens_json, dados["termos"], dados["total"],
             desconto_json, fotos_json, dados["ordem_servico"], dados.get("status", "Rascunho")),
        )
        self.conn.commit()
        return self.cur.lastrowid

    def atualizar_status(self, oid, status):
        self.cur.execute("UPDATE orcamentos SET status=? WHERE id=?", (status, oid))
        self.conn.commit()

    def excluir_orcamento(self, oid):
        self.cur.execute("DELETE FROM orcamentos WHERE id=?", (oid,))
        self.conn.commit()

    # ----------------------------------------------------------------- métricas
    def metricas(self) -> dict:
        self.cur.execute("SELECT COUNT(*) AS n FROM orcamentos")
        n_orc = self.cur.fetchone()["n"]
        self.cur.execute("SELECT COUNT(*) AS n FROM clientes")
        n_cli = self.cur.fetchone()["n"]
        self.cur.execute("SELECT COALESCE(SUM(total),0) AS s FROM orcamentos")
        total = self.cur.fetchone()["s"]
        self.cur.execute(
            "SELECT COALESCE(SUM(total),0) AS s FROM orcamentos WHERE status='Aprovado'"
        )
        aprovado = self.cur.fetchone()["s"]
        return {
            "orcamentos": n_orc,
            "clientes": n_cli,
            "valor_total": total or 0,
            "valor_aprovado": aprovado or 0,
        }

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass
