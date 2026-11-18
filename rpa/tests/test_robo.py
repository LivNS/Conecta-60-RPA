"""Cenários exigidos pelo enunciado (etapa 07): sucesso, decisão e falha."""
import json
import shutil
from datetime import datetime, timezone

import pytest

from conftest import EXEMPLOS, escrever_config, porta_fechada
from rpa_alertas.modelos import ConfiguracaoInvalida, Fonte, ItemBruto
from rpa_alertas.regras import classificar, validar
from rpa_alertas.registro import sanitizar
from rpa_alertas.robo import executar

AGORA = datetime(2026, 11, 16, 21, 0, tzinfo=timezone.utc)
RSS_OK = """<?xml version="1.0"?><rss version="2.0"><channel><title>Feed teste</title>
<item><title>Falso sorteio promete prêmio em dinheiro por mensagem</title>
<link>https://feed.exemplo.org/sorteio</link><pubDate>Sat, 14 Nov 2026 12:00:00 -0300</pubDate>
<description>Mensagem diz que você ganhou um sorteio e pede taxa para liberar o prêmio.</description></item>
<item><title>Falso técnico pede para instalar app de acesso remoto</title>
<link>https://feed.exemplo.org/suporte</link><pubDate>Fri, 13 Nov 2026 09:00:00 -0300</pubDate>
<description>Golpista diz ser do suporte e pede para instalar aplicativo.</description></item>
</channel></rss>""".encode()


def fonte_rss(url, id_="feed-teste"):
    return {"id": id_, "nome": "Feed de teste", "tipo": "rss", "local": url,
            "dominios_permitidos": ["feed.exemplo.org"]}


def ler_log(base, resumo):
    return [json.loads(l) for l in (base / "logs" / resumo["log"]).read_text(encoding="utf-8").splitlines()]


# ---------------- SUCESSO ----------------

def test_sucesso_arquivo_gera_rascunhos_para_o_mvp(base):
    resumo = executar(escrever_config(base), ecoar=False)
    rascunhos = json.loads((base / "saida" / "rascunhos.json").read_text(encoding="utf-8"))
    assert resumo["rascunhos_entregues"] == 5
    assert len(rascunhos) == 5
    assert all(r["status"] == "pendente_revisao" for r in rascunhos)  # nunca publica sozinho
    assert {r["tema"] for r in rascunhos} >= {"banco_falso", "pix_parente", "inss_beneficios",
                                               "codigo_verificacao"}
    assert all(r["como_se_proteger"] for r in rascunhos)
    assert (base / "entrada" / "processados" / "boletim_2026-11-16.json").exists()


def test_sucesso_feed_rss(base, servidor):
    s = servidor(resposta_get=(200, RSS_OK))
    resumo = executar(escrever_config(base, [fonte_rss(s.url)], ativa_arquivo=False), ecoar=False)
    temas = {r["tema"] for r in json.loads((base / "saida" / "rascunhos.json").read_text(encoding="utf-8"))}
    assert resumo["fontes_ok"] == 1 and resumo["rascunhos_entregues"] == 2
    assert temas == {"promocao_falsa", "falso_suporte"}


def test_sucesso_integracao_api_com_token(base, servidor, monkeypatch):
    api = servidor(status_post=201)
    monkeypatch.setenv("RPA_API_TOKEN", "token-de-teste")
    resumo = executar(escrever_config(base, modo="api", api_url=api.url), ecoar=False)
    assert resumo["rascunhos_entregues"] == 5
    assert len(api.recebidos) == 5
    assert api.headers[0]["Authorization"] == "Bearer token-de-teste"
    assert not (base / "estado" / "fila_reenvio.jsonl").exists()


# ---------------- DECISÃO ----------------

def test_decisao_duplicado_no_mesmo_lote_e_entre_execucoes(base):
    caminho = escrever_config(base)
    primeira = executar(caminho, ecoar=False)
    assert primeira["duplicados"] == 1  # mesmo título e link com barra final
    shutil.copy(EXEMPLOS / "boletim_2026-11-16.json", base / "entrada" / "de_novo.json")
    segunda = executar(caminho, ecoar=False)
    assert segunda["rascunhos_entregues"] == 0
    assert segunda["duplicados"] == 6
    assert len(json.loads((base / "saida" / "rascunhos.json").read_text(encoding="utf-8"))) == 5


def test_decisao_itens_invalidos_vao_para_quarentena(base):
    resumo = executar(escrever_config(base), ecoar=False)
    assert resumo["motivos_invalidos"] == {"link_ausente": 1, "data_no_futuro": 1,
                                           "origem_nao_permitida": 1}
    linhas = (base / "estado" / "itens_invalidos.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 3


def test_decisao_sem_tema_vira_rascunho_para_revisar(base):
    executar(escrever_config(base), ecoar=False)
    rascunhos = json.loads((base / "saida" / "rascunhos.json").read_text(encoding="utf-8"))
    sem_tema = [r for r in rascunhos if r["precisa_revisar_tema"]]
    assert len(sem_tema) == 1 and sem_tema[0]["tema"] == "revisar_tema"


@pytest.mark.parametrize("campos,motivo", [
    ({"titulo": "curto"}, "titulo_ausente_ou_curto"),
    ({"link": "ftp://alertas.exemplo.org/x"}, "link_invalido"),
    ({"link": "https://alertas.exemplo.org.golpe.com/x"}, "origem_nao_permitida"),
    ({"data": "ontem"}, "data_invalida"),
    ({"data": "2025-01-01"}, "noticia_antiga"),
])
def test_decisao_regras_de_validacao(campos, motivo):
    fonte = Fonte("f", "F", "arquivo", ".", ["alertas.exemplo.org"])
    dados = {"titulo": "Título suficientemente longo", "link": "https://alertas.exemplo.org/a",
             "data": "2026-11-15", "resumo": "", "fonte_id": "f", "fonte_nome": "F"} | campos
    assert validar(ItemBruto(**dados), fonte, agora=AGORA) == (False, motivo)


def test_decisao_classificacao_escolhe_tema_com_mais_sinais():
    item = ItemBruto("Oi mãe, troquei de número", "", "", "Preciso de um Pix urgente", "f", "F")
    tema, pontos = classificar(item)
    assert tema == "pix_parente" and pontos["pix_parente"] >= 2


# ---------------- FALHA ----------------

def test_falha_fonte_fora_do_ar_nao_derruba_as_outras(base):
    resumo = executar(escrever_config(base, [fonte_rss(porta_fechada())]), ecoar=False)
    assert resumo["fontes_indisponiveis"] == 1
    assert resumo["rascunhos_entregues"] == 5  # a fonte de arquivos seguiu normalmente
    eventos = ler_log(base, resumo)
    assert sum(e["resultado"] == "tentativa_falhou" for e in eventos) == 2
    assert any(e["resultado"] == "fonte_indisponivel" and e["nivel"] == "ERROR" for e in eventos)


def test_falha_feed_corrompido_e_http_500(base, servidor):
    ruim = servidor(resposta_get=(200, b"<rss><channel><item>sem fechar"))
    erro = servidor(resposta_get=(500, b""))
    resumo = executar(escrever_config(base, [fonte_rss(ruim.url, "ruim"), fonte_rss(erro.url, "erro")],
                                      ativa_arquivo=False), ecoar=False)
    assert resumo["fontes_invalidas"] == 1 and resumo["fontes_indisponiveis"] == 1


def test_falha_arquivo_corrompido_vai_para_quarentena(base):
    executar(escrever_config(base), ecoar=False)
    assert (base / "entrada" / "quarentena" / "boletim_corrompido.json").exists()


def test_falha_api_fora_usa_fila_e_reenvia_depois(base, servidor, monkeypatch):
    monkeypatch.setenv("RPA_API_TOKEN", "t")
    url_morta = porta_fechada().rsplit("/", 1)[0]
    caminho = escrever_config(base, modo="api", api_url=url_morta)
    primeira = executar(caminho, ecoar=False)
    assert primeira["na_fila"] == 5 and primeira["rascunhos_entregues"] == 0

    api = servidor(status_post=201)  # a API volta
    monkeypatch.setenv("RPA_API_URL", api.url)
    segunda = executar(caminho, ecoar=False)
    assert segunda["reenviados_da_fila"] == 5
    assert len(api.recebidos) == 5
    assert not (base / "estado" / "fila_reenvio.jsonl").exists()


def test_falha_api_recusa_token_vai_para_fila(base, servidor, monkeypatch):
    api = servidor(status_post=401)
    monkeypatch.setenv("RPA_API_TOKEN", "errado")
    resumo = executar(escrever_config(base, modo="api", api_url=api.url), ecoar=False)
    assert resumo["na_fila"] == 5
    assert any("token recusado" in e["mensagem"] for e in ler_log(base, resumo))


def test_api_responde_409_conta_como_ja_existente(base, servidor, monkeypatch):
    api = servidor(status_post=409)
    monkeypatch.setenv("RPA_API_TOKEN", "t")
    resumo = executar(escrever_config(base, modo="api", api_url=api.url), ecoar=False)
    assert resumo["ja_existiam_no_mvp"] == 5 and resumo["na_fila"] == 0


def test_falha_configuracao_invalida(base, monkeypatch):
    with pytest.raises(ConfiguracaoInvalida):
        executar(base / "config" / "nao_existe.json", ecoar=False)
    monkeypatch.delenv("RPA_API_TOKEN", raising=False)
    with pytest.raises(ConfiguracaoInvalida):
        executar(escrever_config(base, modo="api", api_url="http://x"), ecoar=False)


# ---------------- LGPD nos logs ----------------

def test_logs_mascaram_dados_pessoais():
    texto = "CPF 123.456.789-09, tel (11) 98765-4321, email maria@exemplo.com, Bearer abc123"
    limpo = sanitizar(texto)
    for proibido in ("123.456.789-09", "98765-4321", "maria@exemplo.com", "abc123"):
        assert proibido not in limpo


def test_quarentena_nao_guarda_cpf(base):
    (base / "entrada" / "com_cpf.json").write_text(json.dumps([{
        "titulo": "Cliente 123.456.789-09 recebeu golpe", "link": "", "data": "2026-11-15"}]))
    executar(escrever_config(base), ecoar=False)
    assert "123.456.789-09" not in (base / "estado" / "itens_invalidos.jsonl").read_text(encoding="utf-8")


# ---------------- Fonte geral com filtro de relevância ----------------

RSS_GERAL = """<?xml version="1.0"?><rss version="2.0"><channel><title>Agência</title>
<item><title>Polícia alerta para golpe do falso funcionário de banco contra aposentados</title>
<link>https://agencia.exemplo.org/1</link><pubDate>Sun, 15 Nov 2026 10:00:00 -0300</pubDate>
<description>Criminosos ligam se passando pelo banco e pedem senha.</description></item>
<item><title>Inmet alerta para chuva intensa no Nordeste</title>
<link>https://agencia.exemplo.org/2</link><pubDate>Sun, 15 Nov 2026 11:00:00 -0300</pubDate>
<description>Previsão para o fim de semana.</description></item>
</channel></rss>""".encode()


def test_decisao_fonte_geral_so_repasse_noticia_de_golpe(base, servidor):
    s = servidor(resposta_get=(200, RSS_GERAL))
    fonte = fonte_rss(s.url) | {"dominios_permitidos": ["agencia.exemplo.org"],
                                "palavras_relevancia": ["golpe", "fraude"]}
    resumo = executar(escrever_config(base, [fonte], ativa_arquivo=False), ecoar=False)
    rascunhos = json.loads((base / "saida" / "rascunhos.json").read_text(encoding="utf-8"))
    assert resumo["fora_do_tema"] == 1 and resumo["rascunhos_entregues"] == 1
    assert rascunhos[0]["tema"] == "banco_falso"