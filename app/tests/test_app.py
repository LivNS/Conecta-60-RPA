import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

RASCUNHO = {
    "id": "0ad748e293557124", "titulo": "Mensagens falsas avisam que a conta será bloqueada",
    "tema": "banco_falso", "tema_rotulo": "Falso contato do banco",
    "resumo_simples": "Criminosos enviam SMS com link falso.",
    "como_se_proteger": ["Não clique no link."], "fonte_nome": "Observatório Fictício",
    "link_fonte": "https://alertas.exemplo.org/x", "data_publicacao": "2026-11-15",
    "precisa_revisar_tema": False, "status": "pendente_revisao", "origem": "rpa",
    "criado_em": "2026-11-17T00:00:00+00:00",
}
ROBO = {"Authorization": "Bearer token-teste"}
ADMIN = ("revisor", "senha-teste")


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("RPA_API_TOKEN", "token-teste")
    monkeypatch.setenv("ADMIN_USUARIO", ADMIN[0])
    monkeypatch.setenv("ADMIN_SENHA", ADMIN[1])
    from app_alertas.main import app
    with TestClient(app) as c:
        yield c


def test_robo_envia_rascunho_que_fica_pendente_e_nao_publico(cliente):
    assert cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO).status_code == 201
    assert cliente.get("/api/alertas").json() == []
    pend = cliente.get("/api/alertas/pendentes", auth=ADMIN).json()
    assert [p["id"] for p in pend] == [RASCUNHO["id"]]


def test_rascunho_repetido_responde_409(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    assert cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO).status_code == 409


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer errado"}])
def test_robo_sem_token_valido_e_recusado(cliente, headers):
    assert cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=headers).status_code == 401


def test_rascunho_malformado_e_recusado(cliente):
    ruim = RASCUNHO | {"link_fonte": "nao-e-url", "como_se_proteger": []}
    assert cliente.post("/api/alertas/rascunhos", json=ruim, headers=ROBO).status_code == 422


def test_aprovacao_publica_e_aparece_na_pagina(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    r = cliente.post(f"/revisao/{RASCUNHO['id']}", data={"acao": "aprovar"}, auth=ADMIN,
                     follow_redirects=False)
    assert r.status_code == 303
    assert len(cliente.get("/api/alertas").json()) == 1
    assert RASCUNHO["titulo"] in cliente.get("/alertas").text


def test_rejeicao_exige_motivo_e_nao_publica(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    sem = cliente.post(f"/api/alertas/{RASCUNHO['id']}/rejeitar", json={"motivo": " "}, auth=ADMIN)
    assert sem.status_code == 422
    ok = cliente.post(f"/api/alertas/{RASCUNHO['id']}/rejeitar", json={"motivo": "não confirmado"},
                      auth=ADMIN)
    assert ok.status_code == 200 and cliente.get("/api/alertas").json() == []
    again = cliente.post(f"/api/alertas/{RASCUNHO['id']}/aprovar", auth=ADMIN)
    assert again.status_code == 409


def test_sem_tema_so_publica_com_tema_escolhido(cliente):
    cliente.post("/api/alertas/rascunhos", headers=ROBO, json=RASCUNHO | {
        "tema": "revisar_tema", "tema_rotulo": "Tema a definir", "precisa_revisar_tema": True})
    cliente.post(f"/api/alertas/{RASCUNHO['id']}/aprovar", json={"tema": "outros"}, auth=ADMIN)
    pub = cliente.get("/api/alertas").json()[0]
    assert pub["tema"] == "outros" and pub["precisa_revisar_tema"] is False


def test_revisao_exige_login(cliente):
    assert cliente.get("/revisao").status_code == 401
    assert cliente.get("/revisao", auth=("revisor", "errada")).status_code == 401
    assert cliente.get("/revisao", auth=ADMIN).status_code == 200


def test_dados_iniciais_so_carregam_com_banco_vazio(tmp_path, monkeypatch):
    semente = Path(__file__).resolve().parent.parent / "dados_iniciais" / "alertas_publicados.json"
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "s.db"))
    monkeypatch.setenv("DADOS_INICIAIS", str(semente))
    monkeypatch.setenv("RPA_API_TOKEN", "t")
    from app_alertas.main import app
    with TestClient(app) as c:  # 1º início: banco vazio -> carrega
        assert len(c.get("/api/alertas").json()) == 4
        c.post("/api/alertas/rascunhos", json=RASCUNHO | {"id": "abcdef1234567890"},
               headers={"Authorization": "Bearer t"})
    with TestClient(app) as c:  # 2º início: banco com dados -> não duplica
        assert len(c.get("/api/alertas").json()) == 4
        assert c.get("/saude").json()["alertas"]["pendente_revisao"] == 1


def test_saude(cliente):
    assert cliente.get("/saude").json()["status"] == "ok"
