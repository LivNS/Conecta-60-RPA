"""Entrega dos rascunhos ao MVP.

Modos:
- "api": POST em {api_url}/api/alertas/rascunhos com token (Bearer). Se a API
  falhar, o rascunho vai para a fila local e é reenviado na próxima execução.
- "arquivo": grava/atualiza um JSON estruturado que o MVP importa.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

ENVIADO = "enviado"
JA_EXISTIA = "ja_existia_no_mvp"
FALHOU = "falhou"


class EnvioApi:
    def __init__(self, api_url: str, token: str, timeout_s: float = 10.0):
        self.url = api_url.rstrip("/") + "/api/alertas/rascunhos"
        self.token = token
        self.timeout_s = timeout_s

    def enviar(self, rascunho: dict) -> tuple[str, str]:
        try:
            resp = requests.post(self.url, json=rascunho, timeout=self.timeout_s,
                                 headers={"Authorization": f"Bearer {self.token}"})
        except requests.RequestException as erro:
            return FALHOU, f"API sem resposta ({type(erro).__name__})"
        if resp.status_code in (200, 201):
            return ENVIADO, f"HTTP {resp.status_code}"
        if resp.status_code == 409:
            return JA_EXISTIA, "HTTP 409"
        if resp.status_code in (401, 403):
            return FALHOU, f"HTTP {resp.status_code}: token recusado"
        return FALHOU, f"HTTP {resp.status_code}"


class EnvioArquivo:
    def __init__(self, arquivo: Path):
        self.arquivo = arquivo

    def enviar(self, rascunho: dict) -> tuple[str, str]:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        try:
            atuais = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            atuais = []
        if any(r.get("id") == rascunho["id"] for r in atuais):
            return JA_EXISTIA, "id já presente no arquivo"
        atuais.append(rascunho)
        temp = self.arquivo.with_suffix(".tmp")
        temp.write_text(json.dumps(atuais, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.arquivo)  # escrita atômica: o MVP nunca lê arquivo pela metade
        return ENVIADO, f"gravado em {self.arquivo.name}"


class Fila:
    """Rascunhos que não puderam ser entregues, para reenvio posterior."""

    def __init__(self, arquivo: Path):
        self.arquivo = arquivo

    def carregar(self) -> list[dict]:
        if not self.arquivo.exists():
            return []
        itens = []
        for linha in self.arquivo.read_text(encoding="utf-8").splitlines():
            try:
                itens.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
        return itens

    def regravar(self, itens: list[dict]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        if not itens:
            self.arquivo.unlink(missing_ok=True)
            return
        self.arquivo.write_text(
            "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in itens), encoding="utf-8")
