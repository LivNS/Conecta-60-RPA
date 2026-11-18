"""Logs de auditoria em JSON Lines, sem dados sensíveis.

Cada linha registra: data/hora, execução, etapa, fonte, item, resultado e mensagem.
Antes de gravar, qualquer texto passa por `sanitizar`, que mascara CPF,
telefone, e-mail, números de cartão e tokens.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_PADROES = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARTAO]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}"), "[TELEFONE]"),
    (re.compile(r"(?i)bearer\s+\S+"), "Bearer [TOKEN]"),
]


def sanitizar(texto: str) -> str:
    if not isinstance(texto, str):
        return texto
    for padrao, troca in _PADROES:
        texto = padrao.sub(troca, texto)
    return texto


class Registro:
    def __init__(self, pasta_logs: Path, execucao_id: str, ecoar: bool = True):
        self.execucao_id = execucao_id
        pasta_logs.mkdir(parents=True, exist_ok=True)
        self.arquivo = pasta_logs / f"execucao_{execucao_id}.jsonl"
        self.ecoar = ecoar

    def evento(self, etapa: str, resultado: str, mensagem: str = "",
               fonte: str | None = None, item: str | None = None,
               nivel: str = "INFO") -> dict:
        linha = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "nivel": nivel,
            "execucao": self.execucao_id,
            "etapa": etapa,
            "fonte": fonte,
            "item": item,
            "resultado": resultado,
            "mensagem": sanitizar(mensagem),
        }
        with self.arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        if self.ecoar:
            alvo = f" [{fonte}]" if fonte else ""
            item_txt = f" item={item}" if item else ""
            print(f"{linha['ts']} {nivel:<5} {etapa:<12} {resultado:<20}{alvo}{item_txt} {linha['mensagem']}",
                  file=sys.stderr)
        return linha
