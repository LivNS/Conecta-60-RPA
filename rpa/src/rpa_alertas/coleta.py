"""Coleta de itens nas fontes permitidas.

Dois tipos de fonte:
- "rss": feed RSS 2.0 ou Atom acessado por HTTP, com timeout e novas tentativas.
- "arquivo": pasta com boletins em JSON ou CSV. Arquivos lidos vão para
  `processados/`; arquivos corrompidos vão para `quarentena/`.
"""
from __future__ import annotations

import csv
import json
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from .modelos import Fonte, FonteIndisponivel, FonteInvalida, ItemBruto

ATOM = "{http://www.w3.org/2005/Atom}"


def coletar(fonte: Fonte, tentativas: int = 3, espera_s: float = 2.0,
            timeout_s: float = 10.0, registro=None) -> list[ItemBruto]:
    if fonte.tipo == "rss":
        return _coletar_rss(fonte, tentativas, espera_s, timeout_s, registro)
    if fonte.tipo == "arquivo":
        return _coletar_pasta(fonte, registro)
    raise FonteInvalida(f"tipo de fonte desconhecido: {fonte.tipo}")


# ---------- RSS ----------

def _coletar_rss(fonte, tentativas, espera_s, timeout_s, registro) -> list[ItemBruto]:
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(fonte.local, timeout=timeout_s,
                                headers={"User-Agent": "rpa-alertas-gs-fiap/0.1"})
            if resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            if resp.status_code >= 400:
                # erro do lado do cliente não melhora com nova tentativa
                raise FonteIndisponivel(f"HTTP {resp.status_code}")
            return _ler_feed(resp.content, fonte)
        except FonteIndisponivel:
            raise
        except (requests.RequestException,) as erro:
            ultimo_erro = erro
            if registro:
                registro.evento("coleta", "tentativa_falhou",
                                f"tentativa {tentativa}/{tentativas}: {type(erro).__name__}",
                                fonte=fonte.id, nivel="WARN")
            if tentativa < tentativas:
                time.sleep(espera_s * tentativa)
    raise FonteIndisponivel(f"sem resposta após {tentativas} tentativas ({type(ultimo_erro).__name__})")


def _texto(elem, *nomes) -> str:
    for nome in nomes:
        achado = elem.find(nome)
        if achado is not None:
            if achado.text:
                return achado.text.strip()
            href = achado.get("href")
            if href:
                return href.strip()
    return ""


def _ler_feed(conteudo: bytes, fonte: Fonte) -> list[ItemBruto]:
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as erro:
        raise FonteInvalida(f"feed ilegível: {erro}") from erro

    itens = raiz.findall("./channel/item") or raiz.findall(f"{ATOM}entry")
    if not itens and raiz.tag not in ("rss", f"{ATOM}feed"):
        raise FonteInvalida("conteúdo não é RSS nem Atom")
    saida = []
    for it in itens:
        saida.append(ItemBruto(
            titulo=_texto(it, "title", f"{ATOM}title"),
            link=_texto(it, "link", f"{ATOM}link"),
            data=_texto(it, "pubDate", f"{ATOM}updated", f"{ATOM}published"),
            resumo=_texto(it, "description", f"{ATOM}summary", f"{ATOM}content"),
            fonte_id=fonte.id,
            fonte_nome=fonte.nome,
        ))
    return saida


# ---------- Pasta de arquivos ----------

def _coletar_pasta(fonte: Fonte, registro) -> list[ItemBruto]:
    pasta = Path(fonte.local)
    if not pasta.is_dir():
        raise FonteIndisponivel(f"pasta de entrada ausente: {pasta}")
    arquivos = sorted(p for p in pasta.iterdir()
                      if p.is_file() and p.suffix.lower() in (".json", ".csv"))
    itens: list[ItemBruto] = []
    for arq in arquivos:  # repetição sobre a coleção de arquivos
        try:
            linhas = _ler_json(arq) if arq.suffix.lower() == ".json" else _ler_csv(arq)
        except FonteInvalida as erro:
            _mover(arq, pasta / "quarentena")
            if registro:
                registro.evento("coleta", "arquivo_quarentena", str(erro),
                                fonte=fonte.id, item=arq.name, nivel="WARN")
            continue
        for linha in linhas:
            itens.append(ItemBruto(
                titulo=str(linha.get("titulo", "") or "").strip(),
                link=str(linha.get("link", "") or "").strip(),
                data=str(linha.get("data", "") or "").strip(),
                resumo=str(linha.get("resumo", "") or "").strip(),
                fonte_id=fonte.id,
                fonte_nome=str(linha.get("orgao") or fonte.nome),
            ))
        _mover(arq, pasta / "processados")
        if registro:
            registro.evento("coleta", "arquivo_lido", f"{len(linhas)} itens",
                            fonte=fonte.id, item=arq.name)
    return itens


def _ler_json(arq: Path) -> list[dict]:
    try:
        dados = json.loads(arq.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise FonteInvalida(f"JSON inválido: {erro}") from erro
    if isinstance(dados, dict):
        dados = dados.get("itens")
    if not isinstance(dados, list) or not all(isinstance(d, dict) for d in dados):
        raise FonteInvalida("JSON sem lista de itens")
    return dados


def _ler_csv(arq: Path) -> list[dict]:
    try:
        with arq.open(encoding="utf-8", newline="") as f:
            leitor = csv.DictReader(f)
            if not leitor.fieldnames or not {"titulo", "link", "data"} <= set(leitor.fieldnames):
                raise FonteInvalida("CSV sem as colunas titulo, link e data")
            return list(leitor)
    except (csv.Error, UnicodeDecodeError) as erro:
        raise FonteInvalida(f"CSV inválido: {erro}") from erro


def _mover(arq: Path, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    shutil.move(str(arq), str(destino / arq.name))
