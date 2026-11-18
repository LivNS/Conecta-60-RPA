import json
import os
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

EXEMPLOS = RAIZ / "exemplos" / "entrada"

# servidores de teste rodam na própria máquina: nunca passar por proxy
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"


@pytest.fixture(autouse=True)
def isolar_ambiente(monkeypatch):
    """Cada teste começa sem as variáveis da demonstração (modo, URL e token da API).

    Sem isso, um terminal com RPA_MODO_ENTREGA/RPA_API_URL ligados faria os testes
    mandarem rascunhos para o app de verdade em vez dos servidores de teste.
    """
    for var in ("RPA_MODO_ENTREGA", "RPA_API_URL", "RPA_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def base(tmp_path):
    """Cria uma pasta de trabalho isolada com config e entrada de exemplo."""
    (tmp_path / "config").mkdir()
    (tmp_path / "entrada").mkdir()
    for arq in EXEMPLOS.iterdir():
        shutil.copy(arq, tmp_path / "entrada" / arq.name)
    return tmp_path


def escrever_config(base: Path, fontes_extra=None, modo="arquivo", api_url="", ativa_arquivo=True):
    cfg = {
        "modo_entrega": modo,
        "api_url": api_url,
        "arquivo_saida": "saida/rascunhos.json",
        "coleta": {"tentativas": 2, "espera_s": 0, "timeout_s": 2},
        "fontes": [{
            "id": "boletins", "nome": "Boletins simulados", "tipo": "arquivo", "local": "entrada",
            "dominios_permitidos": ["alertas.exemplo.org", "seguranca.exemplo.gov.br"],
            "ativa": ativa_arquivo,
        }] + (fontes_extra or []),
    }
    caminho = base / "config" / "fontes.json"
    caminho.write_text(json.dumps(cfg), encoding="utf-8")
    return caminho


class Servidor:
    """Servidor HTTP local para simular feed RSS e a API do MVP."""

    def __init__(self, resposta_get=(200, b""), status_post=201):
        self.resposta_get = resposta_get
        self.status_post = status_post
        self.recebidos = []
        self.headers = []
        dono = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, corpo = dono.resposta_get
                self.send_response(status)
                self.send_header("Content-Type", "application/rss+xml")
                self.end_headers()
                self.wfile.write(corpo)

            def do_POST(self):
                tamanho = int(self.headers.get("Content-Length", 0))
                dono.recebidos.append(json.loads(self.rfile.read(tamanho)))
                dono.headers.append(dict(self.headers))
                self.send_response(dono.status_post)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def parar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def servidor():
    criados = []

    def criar(**kw):
        s = Servidor(**kw)
        criados.append(s)
        return s

    yield criar
    for s in criados:
        s.parar()


def porta_fechada() -> str:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{porta}/rss"
