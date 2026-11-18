"""Roda os três cenários de teste exigidos (sucesso, decisão, falha) e guarda evidências.

Uso (a partir da pasta rpa/):  python scripts/demonstrar_cenarios.py
Saída: evidencias/<cenario>/ com config, logs JSONL, resumo e rascunhos gerados.
Uma API falsa local simula o MVP para mostrar fila e reenvio sem depender da internet.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

from rpa_alertas.robo import executar  # noqa: E402

EXEMPLOS = RAIZ / "exemplos" / "entrada"
SAIDA = RAIZ / "evidencias"


def preparar(nome: str, modo="arquivo", api_url="", fontes_extra=None) -> Path:
    pasta = SAIDA / nome
    shutil.rmtree(pasta, ignore_errors=True)
    (pasta / "config").mkdir(parents=True)
    shutil.copytree(EXEMPLOS, pasta / "entrada")
    cfg = {
        "modo_entrega": modo, "api_url": api_url, "arquivo_saida": "saida/rascunhos.json",
        "coleta": {"tentativas": 3, "espera_s": 0.5, "timeout_s": 3},
        "fontes": [{"id": "boletins-simulados", "nome": "Boletins simulados (fictícios)",
                    "tipo": "arquivo", "local": "entrada",
                    "dominios_permitidos": ["alertas.exemplo.org", "seguranca.exemplo.gov.br"]}]
        + (fontes_extra or []),
    }
    caminho = pasta / "config" / "fontes.json"
    caminho.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def subir_api_falsa(porta: int, recebidos: list):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            recebidos.append(json.loads(self.rfile.read(n)))
            self.send_response(201)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", porta), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def titulo(t: str):
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}", flush=True)


def main():
    SAIDA.mkdir(exist_ok=True)

    titulo("CENÁRIO 1 — SUCESSO: boletins válidos viram rascunhos para revisão")
    r1 = executar(preparar("1_sucesso"))

    titulo("CENÁRIO 2 — DECISÃO: o mesmo boletim chega de novo e nada é duplicado")
    caminho = preparar("2_decisao")
    executar(caminho, ecoar=False)
    shutil.copy(EXEMPLOS / "boletim_2026-11-16.json", caminho.parent.parent / "entrada" / "reenvio_do_orgao.json")
    r2 = executar(caminho)

    titulo("CENÁRIO 3 — FALHA: fonte RSS fora do ar e API do MVP desligada")
    porta_api = porta_livre()
    os.environ["RPA_API_TOKEN"] = "token-de-demonstracao"
    caminho = preparar("3_falha", modo="api", api_url=f"http://127.0.0.1:{porta_api}", fontes_extra=[{
        "id": "feed-fora-do-ar", "nome": "Feed que não responde", "tipo": "rss",
        "local": f"http://127.0.0.1:{porta_livre()}/rss", "dominios_permitidos": ["exemplo.org"]}])
    r3a = executar(caminho)

    titulo("CENÁRIO 3 (cont.) — A API volta: a fila é reenviada automaticamente")
    recebidos: list = []
    srv = subir_api_falsa(porta_api, recebidos)
    try:
        r3b = executar(caminho)
    finally:
        srv.shutdown()

    titulo("RESUMO DAS EVIDÊNCIAS")
    print(f"1 sucesso : {r1['rascunhos_entregues']} rascunhos, {r1['itens_invalidos']} inválidos, "
          f"{r1['sem_tema']} para revisar tema")
    print(f"2 decisão : {r2['duplicados']} duplicados ignorados, {r2['rascunhos_entregues']} novos")
    print(f"3 falha   : {r3a['fontes_indisponiveis']} fonte fora do ar, {r3a['na_fila']} na fila")
    print(f"3 reenvio : {r3b['reenviados_da_fila']} reenviados; API recebeu {len(recebidos)}")
    print(f"Arquivos em: {SAIDA}")


if __name__ == "__main__":
    main()
