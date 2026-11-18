"""Persistência dos alertas em SQLite (arquivo definido por DATABASE_PATH)."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

ESQUEMA = """
CREATE TABLE IF NOT EXISTS alertas (
    id TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    tema TEXT NOT NULL,
    tema_rotulo TEXT NOT NULL,
    resumo_simples TEXT NOT NULL,
    como_se_proteger TEXT NOT NULL,          -- lista em JSON
    fonte_nome TEXT NOT NULL,
    link_fonte TEXT NOT NULL,
    data_publicacao TEXT,
    precisa_revisar_tema INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pendente_revisao',  -- pendente_revisao | publicado | rejeitado
    origem TEXT NOT NULL DEFAULT 'rpa',
    criado_em TEXT NOT NULL,
    recebido_em TEXT NOT NULL,
    revisado_em TEXT,
    motivo_rejeicao TEXT
);
"""


def caminho_banco() -> str:
    return os.environ.get("DATABASE_PATH", "dados/alertas.db")


@contextmanager
def conectar():
    caminho = caminho_banco()
    if caminho != ":memory:":
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def iniciar() -> None:
    with conectar() as con:
        con.executescript(ESQUEMA)


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _linha(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["como_se_proteger"] = json.loads(d["como_se_proteger"])
    d["precisa_revisar_tema"] = bool(d["precisa_revisar_tema"])
    return d


def inserir_rascunho(r: dict) -> bool:
    """Retorna False se o id já existe (o robô trata como 409)."""
    with conectar() as con:
        try:
            con.execute(
                """INSERT INTO alertas (id, titulo, tema, tema_rotulo, resumo_simples, como_se_proteger,
                   fonte_nome, link_fonte, data_publicacao, precisa_revisar_tema, status, origem,
                   criado_em, recebido_em) VALUES (?,?,?,?,?,?,?,?,?,?, 'pendente_revisao', ?, ?, ?)""",
                (r["id"], r["titulo"], r["tema"], r["tema_rotulo"], r["resumo_simples"],
                 json.dumps(r["como_se_proteger"], ensure_ascii=False), r["fonte_nome"], r["link_fonte"],
                 r.get("data_publicacao") or "", int(r["precisa_revisar_tema"]), r.get("origem", "rpa"),
                 r["criado_em"], agora()))
        except sqlite3.IntegrityError:
            return False
    return True


def listar(status: str) -> list[dict]:
    ordem = "data_publicacao DESC, recebido_em DESC" if status == "publicado" else "recebido_em ASC"
    with conectar() as con:
        rows = con.execute(f"SELECT * FROM alertas WHERE status = ? ORDER BY {ordem}", (status,)).fetchall()
    return [_linha(r) for r in rows]


def obter(id_: str) -> dict | None:
    with conectar() as con:
        r = con.execute("SELECT * FROM alertas WHERE id = ?", (id_,)).fetchone()
    return _linha(r) if r else None


def revisar(id_: str, aprovar: bool, motivo: str = "", tema: str | None = None,
            tema_rotulo: str | None = None) -> str:
    """Retorna 'ok', 'nao_encontrado' ou 'ja_revisado'."""
    with conectar() as con:
        r = con.execute("SELECT status FROM alertas WHERE id = ?", (id_,)).fetchone()
        if r is None:
            return "nao_encontrado"
        if r["status"] != "pendente_revisao":
            return "ja_revisado"
        if aprovar:
            if tema:
                con.execute("UPDATE alertas SET tema = ?, tema_rotulo = ?, precisa_revisar_tema = 0 "
                            "WHERE id = ?", (tema, tema_rotulo, id_))
            con.execute("UPDATE alertas SET status = 'publicado', revisado_em = ? WHERE id = ?",
                        (agora(), id_))
        else:
            con.execute("UPDATE alertas SET status = 'rejeitado', revisado_em = ?, motivo_rejeicao = ? "
                        "WHERE id = ?", (agora(), motivo[:300], id_))
    return "ok"


def carregar_iniciais(arquivo: str) -> int:
    """Se o banco estiver vazio, publica os alertas de demonstração do arquivo.

    Servidores gratuitos apagam o disco ao reiniciar; isso evita uma página pública vazia.
    Retorna quantos alertas foram carregados (0 se o banco já tinha dados ou o arquivo não existe).
    """
    if not arquivo or not os.path.exists(arquivo):
        return 0
    with conectar() as con:
        if con.execute("SELECT COUNT(*) FROM alertas").fetchone()[0]:
            return 0
    with open(arquivo, encoding="utf-8") as f:
        alertas = json.load(f).get("alertas", [])
    n = 0
    for a in alertas:
        if inserir_rascunho(a | {"origem": a.get("origem", "rpa")}):
            revisar(a["id"], True)
            n += 1
    return n


def contagem() -> dict:
    with conectar() as con:
        rows = con.execute("SELECT status, COUNT(*) n FROM alertas GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}
