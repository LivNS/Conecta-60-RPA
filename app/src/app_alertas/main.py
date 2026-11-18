"""MVP — módulo de alertas: recebe rascunhos do robô RPA, revisão humana e publicação.

Variáveis de ambiente:
  RPA_API_TOKEN   token que o robô usa no POST de rascunhos (obrigatório)
  ADMIN_USUARIO / ADMIN_SENHA   acesso à tela de revisão (obrigatório)
  DATABASE_PATH   arquivo SQLite (padrão dados/alertas.db)
  APP_NOME        nome exibido do produto
"""
from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, HttpUrl

from . import banco

AQUI = Path(__file__).resolve().parent
TEMAS = {
    "banco_falso": "Falso contato do banco",
    "pix_parente": "Pedido de dinheiro de falso parente",
    "codigo_verificacao": "Pedido de código de verificação",
    "falso_suporte": "Falso suporte técnico",
    "promocao_falsa": "Falsa promoção ou prêmio",
    "inss_beneficios": "Golpe com aposentadoria ou benefício",
    "outros": "Outros golpes",
}

@asynccontextmanager
async def ciclo_de_vida(_app):
    banco.iniciar()
    banco.carregar_iniciais(os.environ.get("DADOS_INICIAIS", ""))
    yield


app = FastAPI(title="Alertas de golpes — API do MVP", version="0.1.0", lifespan=ciclo_de_vida)
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
templates = Jinja2Templates(directory=AQUI / "templates")
bearer = HTTPBearer(auto_error=False)
basic = HTTPBasic(realm="Revisao de alertas")


def nome_app() -> str:
    return os.environ.get("APP_NOME", "Conecta 60+")


# ---------- segurança ----------

def exigir_robo(cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    esperado = os.environ.get("RPA_API_TOKEN", "")
    if not esperado:
        raise HTTPException(503, "RPA_API_TOKEN não configurado no servidor")
    if cred is None or not secrets.compare_digest(cred.credentials.encode(), esperado.encode()):
        raise HTTPException(401, "token inválido", headers={"WWW-Authenticate": "Bearer"})


def exigir_revisor(cred: Annotated[HTTPBasicCredentials, Depends(basic)]) -> str:
    usuario, senha = os.environ.get("ADMIN_USUARIO", ""), os.environ.get("ADMIN_SENHA", "")
    if not usuario or not senha:
        raise HTTPException(503, "ADMIN_USUARIO/ADMIN_SENHA não configurados no servidor")
    ok = secrets.compare_digest(cred.username.encode(), usuario.encode()) and \
        secrets.compare_digest(cred.password.encode(), senha.encode())
    if not ok:
        raise HTTPException(401, "acesso negado", headers={"WWW-Authenticate": "Basic"})
    return cred.username


# ---------- contrato com o robô ----------

class RascunhoEntrada(BaseModel):
    id: str = Field(min_length=8, max_length=64, pattern=r"^[a-f0-9]+$")
    titulo: str = Field(min_length=10, max_length=300)
    tema: str = Field(max_length=40)
    tema_rotulo: str = Field(max_length=120)
    resumo_simples: str = Field(min_length=1, max_length=600)
    como_se_proteger: list[str] = Field(min_length=1, max_length=6)
    fonte_nome: str = Field(max_length=200)
    link_fonte: HttpUrl
    data_publicacao: str = ""
    precisa_revisar_tema: bool = False
    status: str = "pendente_revisao"
    origem: str = "rpa"
    criado_em: str


@app.post("/api/alertas/rascunhos", status_code=201, dependencies=[Depends(exigir_robo)])
def receber_rascunho(r: RascunhoEntrada):
    dados = r.model_dump()
    dados["link_fonte"] = str(r.link_fonte)
    if not banco.inserir_rascunho(dados):
        raise HTTPException(409, "rascunho já recebido")
    return {"id": r.id, "status": "pendente_revisao"}


@app.get("/api/alertas")
def alertas_publicados():
    return banco.listar("publicado")


@app.get("/api/alertas/pendentes", dependencies=[Depends(exigir_revisor)])
def alertas_pendentes():
    return banco.listar("pendente_revisao")


class Decisao(BaseModel):
    motivo: str = ""
    tema: str | None = None


def _aplicar(id_: str, aprovar: bool, motivo: str = "", tema: str | None = None):
    if tema and tema not in TEMAS:
        raise HTTPException(422, "tema desconhecido")
    if not aprovar and not motivo.strip():
        raise HTTPException(422, "informe o motivo da rejeição")
    res = banco.revisar(id_, aprovar, motivo, tema, TEMAS.get(tema) if tema else None)
    if res == "nao_encontrado":
        raise HTTPException(404, "alerta não encontrado")
    if res == "ja_revisado":
        raise HTTPException(409, "alerta já revisado")


@app.post("/api/alertas/{id_}/aprovar", dependencies=[Depends(exigir_revisor)])
def aprovar(id_: str, d: Decisao | None = None):
    _aplicar(id_, True, tema=(d.tema if d else None))
    return {"id": id_, "status": "publicado"}


@app.post("/api/alertas/{id_}/rejeitar", dependencies=[Depends(exigir_revisor)])
def rejeitar(id_: str, d: Decisao):
    _aplicar(id_, False, motivo=d.motivo)
    return {"id": id_, "status": "rejeitado"}


@app.get("/saude")
def saude():
    return {"status": "ok", "alertas": banco.contagem()}


# ---------- páginas ----------

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return templates.TemplateResponse(request, "inicio.html", {"app_nome": nome_app()})


@app.get("/alertas", response_class=HTMLResponse)
def pagina_alertas(request: Request):
    return templates.TemplateResponse(request, "alertas.html",
                                      {"app_nome": nome_app(), "alertas": banco.listar("publicado")})


@app.get("/revisao", response_class=HTMLResponse)
def pagina_revisao(request: Request, usuario: Annotated[str, Depends(exigir_revisor)], msg: str = ""):
    return templates.TemplateResponse(request, "revisao.html", {
        "app_nome": nome_app(), "pendentes": banco.listar("pendente_revisao"),
        "temas": TEMAS, "msg": msg, "contagem": banco.contagem()})


@app.post("/revisao/{id_}", dependencies=[Depends(exigir_revisor)])
def decidir_pela_tela(id_: str, acao: Annotated[str, Form()], motivo: Annotated[str, Form()] = "",
                      tema: Annotated[str, Form()] = ""):
    try:
        _aplicar(id_, acao == "aprovar", motivo=motivo, tema=tema or None)
    except HTTPException as e:
        return RedirectResponse(f"/revisao?msg=Erro:+{e.detail}", status_code=status.HTTP_303_SEE_OTHER)
    texto = "Alerta+publicado" if acao == "aprovar" else "Alerta+rejeitado"
    return RedirectResponse(f"/revisao?msg={texto}", status_code=status.HTTP_303_SEE_OTHER)
