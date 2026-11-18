"""Evidência de integração RPA -> MVP, de ponta a ponta, com prints.

1. Sobe o app (uvicorn) com banco limpo.
2. Roda o robô em modo "api" contra o app de verdade.
3. Abre a tela de revisão no navegador, aprova 4 rascunhos (escolhendo o tema do que veio sem tema)
   e rejeita 1 com motivo, clicando nos botões como um revisor faria.
4. Abre a página pública de alertas (computador e celular).
5. Roda o robô de novo para mostrar o 409 (já existia no MVP) e a deduplicação.
Saída: rpa/assets/*.png e rpa/evidencias/4_integracao/.

Uso (raiz do repositório): python scripts/integracao_ponta_a_ponta.py
"""
from __future__ import annotations

import html
import io
import json
import os
import shutil
import socket
import sys
import threading
import time
from contextlib import redirect_stderr
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "rpa" / "src"))
sys.path.insert(0, str(RAIZ / "app" / "src"))
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

EVID = RAIZ / "rpa" / "evidencias" / "4_integracao"
ASSETS = RAIZ / "rpa" / "assets"
TOKEN = "token-de-demonstracao-integracao"
ADMIN = ("revisor", "senha-demonstracao")
CHROME = "/usr/bin/google-chrome"


def porta_livre() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def subir_app(porta: int):
    import uvicorn
    from app_alertas.main import app
    cfg = uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning")
    srv = uvicorn.Server(cfg)
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(50):
        if srv.started:
            return srv
        time.sleep(0.1)
    raise RuntimeError("app não subiu")


def terminal_png(titulo: str, texto: str, destino: Path, pagina):
    linhas = []
    for l in texto.splitlines():
        cor = "#ff7b72" if " ERROR " in l else "#e3b341" if " WARN " in l else "#c9d1d9"
        linhas.append(f'<span style="color:{cor}">{html.escape(l)}</span>')
    doc = f"""<html><body style="margin:0;background:#0d1117;font:13px/1.45 'DejaVu Sans Mono',monospace">
<div style="padding:10px 14px;background:#161b22;color:#8b949e;font-family:Arial">{html.escape(titulo)}</div>
<pre style="margin:0;padding:12px 14px;white-space:pre-wrap">{chr(10).join(linhas)}</pre></body></html>"""
    pagina.set_viewport_size({"width": 1400, "height": 300})
    pagina.set_content(doc)
    pagina.screenshot(path=str(destino), full_page=True)


def rodar_robo(caminho_cfg: Path) -> tuple[dict, str]:
    from rpa_alertas.robo import executar
    buf = io.StringIO()
    with redirect_stderr(buf):
        resumo = executar(caminho_cfg, ecoar=True)
    return resumo, buf.getvalue()


def main():
    from playwright.sync_api import sync_playwright

    shutil.rmtree(EVID, ignore_errors=True)
    (EVID / "config").mkdir(parents=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copytree(RAIZ / "rpa" / "exemplos" / "entrada", EVID / "entrada")

    porta = porta_livre()
    url = f"http://127.0.0.1:{porta}"
    os.environ.update({"DATABASE_PATH": str(EVID / "app.db"), "RPA_API_TOKEN": TOKEN,
                       "ADMIN_USUARIO": ADMIN[0], "ADMIN_SENHA": ADMIN[1], "APP_NOME": os.environ.get("APP_NOME", "Conecta 60+")})
    os.environ.pop("RPA_API_URL", None)
    cfg = {"modo_entrega": "api", "api_url": url,
           "coleta": {"tentativas": 2, "espera_s": 0.2, "timeout_s": 3},
           "fontes": [{"id": "boletins-simulados", "nome": "Boletins simulados (fictícios)", "tipo": "arquivo",
                       "local": "entrada", "dominios_permitidos": ["alertas.exemplo.org", "seguranca.exemplo.gov.br"]}]}
    caminho = EVID / "config" / "fontes.json"
    caminho.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    srv = subir_app(porta)
    try:
        resumo1, saida1 = rodar_robo(caminho)
        print(saida1)
        assert resumo1["rascunhos_entregues"] == 5, resumo1

        with sync_playwright() as p:
            nav = p.chromium.launch(executable_path=CHROME)
            term = nav.new_page()
            terminal_png(f"$ python -m rpa_alertas --config config/fontes.json   (modo api -> {url})",
                         saida1 + "\n" + json.dumps(resumo1, ensure_ascii=False, indent=2),
                         ASSETS / "01_robo_execucao_api.png", term)

            ctx = nav.new_context(http_credentials={"username": ADMIN[0], "password": ADMIN[1]},
                                  viewport={"width": 1100, "height": 900}, locale="pt-BR")
            pg = ctx.new_page()
            pg.goto(f"{url}/revisao")
            pg.screenshot(path=str(ASSETS / "02_tela_revisao_pendentes.png"), full_page=True)

            # rejeita o alerta do INSS com motivo (demonstra a decisão humana)
            card = pg.locator("article", has_text="INSS")
            card.locator("textarea").fill("Demonstração: informação ainda não confirmada na fonte oficial.")
            card.get_by_role("button", name="Rejeitar").click()
            pg.wait_for_load_state()
            # o rascunho sem tema exige escolher o tema antes de publicar
            card = pg.locator("article", has_text="cartório")
            card.locator("select").select_option("outros")
            pg.screenshot(path=str(ASSETS / "03_revisao_tema_escolhido.png"), full_page=True)
            card.get_by_role("button", name="Aprovar e publicar").click()
            pg.wait_for_load_state()
            while pg.get_by_role("button", name="Aprovar e publicar").count():
                pg.get_by_role("button", name="Aprovar e publicar").first.click()
                pg.wait_for_load_state()
            pg.screenshot(path=str(ASSETS / "04_revisao_concluida.png"), full_page=True)

            pub = nav.new_page(viewport={"width": 1100, "height": 900}, locale="pt-BR")
            pub.goto(f"{url}/alertas")
            pub.screenshot(path=str(ASSETS / "05_alertas_publicados_computador.png"), full_page=True)
            cel = nav.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="pt-BR")
            cel.goto(f"{url}/alertas")
            cel.screenshot(path=str(ASSETS / "06_alertas_publicados_celular.png"))

            resumo2, saida2 = rodar_robo(caminho)  # nenhum arquivo novo: nada a reenviar
            shutil.copy(RAIZ / "rpa" / "exemplos" / "entrada" / "boletim_2026-11-16.json",
                        EVID / "entrada" / "mesmo_boletim_de_novo.json")
            resumo3, saida3 = rodar_robo(caminho)
            terminal_png("$ python -m rpa_alertas   (mesmo boletim chega de novo: deduplicação)",
                         saida3 + "\n" + json.dumps(resumo3, ensure_ascii=False, indent=2),
                         ASSETS / "07_robo_deduplicacao.png", term)
            nav.close()

        import urllib.request
        publicados = json.load(urllib.request.urlopen(f"{url}/api/alertas"))
        saude = json.load(urllib.request.urlopen(f"{url}/saude"))
        relato = {"url_app": url, "execucao_1": resumo1, "execucao_3": resumo3,
                  "alertas_publicados": len(publicados), "situacao_no_app": saude["alertas"]}
        (EVID / "relato_integracao.json").write_text(json.dumps(relato, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
        print(json.dumps(relato["situacao_no_app"], ensure_ascii=False))
        assert saude["alertas"] == {"publicado": 4, "rejeitado": 1}, saude
        assert resumo3["duplicados"] == 6 and resumo3["rascunhos_entregues"] == 0
        print("INTEGRAÇÃO OK — prints em", ASSETS)
    finally:
        srv.should_exit = True


if __name__ == "__main__":
    main()
