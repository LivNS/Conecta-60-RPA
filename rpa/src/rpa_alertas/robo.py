"""Orquestração do robô: do gatilho até o rascunho entregue ao MVP.

Fluxo (ver docs/fluxo-bpmn):
 1. Carrega configuração e lista de fontes permitidas.
 2. Reenvia rascunhos que ficaram na fila em execuções anteriores.
 3. Para cada fonte ativa: coleta (com novas tentativas). Falha -> registra e segue.
 4. Para cada item coletado: valida -> deduplica -> classifica tema -> monta rascunho -> entrega.
 5. Grava resumo da execução e o estado de itens já vistos.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .coleta import coletar
from .envio import ENVIADO, FALHOU, JA_EXISTIA, EnvioApi, EnvioArquivo, Fila
from .modelos import ConfiguracaoInvalida, Fonte, FonteIndisponivel, FonteInvalida
from .rascunho import montar
from .regras import Vistos, chave_item, classificar, relevante, validar
from .registro import Registro, sanitizar


def carregar_config(caminho: Path) -> tuple[dict, list[Fonte], Path]:
    try:
        cfg = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError as erro:
        raise ConfiguracaoInvalida(f"configuração não encontrada: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise ConfiguracaoInvalida(f"configuração com JSON inválido: {erro}") from erro
    base = caminho.resolve().parent.parent
    fontes = []
    for f in cfg.get("fontes", []):
        faltando = {"id", "nome", "tipo", "local", "dominios_permitidos"} - set(f)
        if faltando:
            raise ConfiguracaoInvalida(f"fonte sem campos {sorted(faltando)}: {f.get('id')}")
        local = f["local"]
        if f["tipo"] == "arquivo" and not Path(local).is_absolute():
            local = str(base / local)
        fontes.append(Fonte(id=f["id"], nome=f["nome"], tipo=f["tipo"], local=local,
                            dominios_permitidos=[d.lower() for d in f["dominios_permitidos"]],
                            ativa=f.get("ativa", True),
                            palavras_relevancia=f.get("palavras_relevancia", [])))
    if not fontes:
        raise ConfiguracaoInvalida("nenhuma fonte configurada")
    return cfg, fontes, base


def _entregador(cfg: dict, base: Path):
    modo = os.environ.get("RPA_MODO_ENTREGA") or cfg.get("modo_entrega", "arquivo")
    if modo == "api":
        token = os.environ.get("RPA_API_TOKEN", "")
        url = os.environ.get("RPA_API_URL") or cfg.get("api_url", "")
        if not token or not url:
            raise ConfiguracaoInvalida("modo api exige RPA_API_TOKEN e api_url (ou RPA_API_URL)")
        return EnvioApi(url, token, cfg.get("coleta", {}).get("timeout_s", 10)), modo
    if modo == "arquivo":
        return EnvioArquivo(base / cfg.get("arquivo_saida", "saida/rascunhos.json")), modo
    raise ConfiguracaoInvalida(f"modo_entrega desconhecido: {modo}")


def executar(caminho_config: Path, ecoar: bool = True) -> dict:
    execucao_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    cfg, fontes, base = carregar_config(caminho_config)
    pastas = cfg.get("pastas", {})
    registro = Registro(base / pastas.get("logs", "logs"), execucao_id, ecoar=ecoar)
    estado = base / pastas.get("estado", "estado")
    vistos = Vistos(estado / "vistos.json")
    fila = Fila(estado / "fila_reenvio.jsonl")
    quarentena = estado / "itens_invalidos.jsonl"
    entregador, modo = _entregador(cfg, base)
    coleta_cfg = cfg.get("coleta", {})
    c = Counter()
    motivos_invalidos = Counter()

    registro.evento("inicio", "ok", f"modo de entrega: {modo}; {len(fontes)} fontes configuradas")

    # 2. Reenvio da fila (resiliência a falhas da API em execuções anteriores)
    pendentes = fila.carregar()
    if pendentes:
        restantes = []
        for rasc in pendentes:
            resultado, msg = entregador.enviar(rasc)
            if resultado == FALHOU:
                restantes.append(rasc)
                c["fila_ainda_pendente"] += 1
            else:
                c["reenviados_da_fila"] += 1
            registro.evento("reenvio", resultado, msg, item=rasc.get("id"),
                            nivel="WARN" if resultado == FALHOU else "INFO")
        fila.regravar(restantes)

    # 3. Repetição sobre as fontes
    for fonte in fontes:
        if not fonte.ativa:
            registro.evento("coleta", "fonte_inativa", "ignorada pela configuração", fonte=fonte.id)
            continue
        try:
            itens = coletar(fonte, tentativas=coleta_cfg.get("tentativas", 3),
                            espera_s=coleta_cfg.get("espera_s", 2.0),
                            timeout_s=coleta_cfg.get("timeout_s", 10.0), registro=registro)
        except FonteIndisponivel as erro:
            c["fontes_indisponiveis"] += 1
            registro.evento("coleta", "fonte_indisponivel", str(erro), fonte=fonte.id, nivel="ERROR")
            continue
        except FonteInvalida as erro:
            c["fontes_invalidas"] += 1
            registro.evento("coleta", "fonte_invalida", str(erro), fonte=fonte.id, nivel="ERROR")
            continue
        c["fontes_ok"] += 1
        c["itens_coletados"] += len(itens)
        registro.evento("coleta", "ok", f"{len(itens)} itens", fonte=fonte.id)

        # 4. Repetição sobre os itens
        for item in itens:
            chave = chave_item(item)
            try:
                ok, motivo = validar(item, fonte)
                if not ok:  # decisão 1: item válido?
                    c["itens_invalidos"] += 1
                    motivos_invalidos[motivo] += 1
                    _quarentenar(quarentena, item, motivo, execucao_id)
                    registro.evento("validacao", "invalido", motivo, fonte=fonte.id, item=chave,
                                    nivel="WARN")
                    continue
                if not relevante(item, fonte):  # decisão 2: fala de golpe?
                    c["fora_do_tema"] += 1
                    registro.evento("relevancia", "fora_do_tema", "sem palavras de golpe/fraude",
                                    fonte=fonte.id, item=chave)
                    continue
                if vistos.contem(chave):  # decisão 3: já processado?
                    c["duplicados"] += 1
                    registro.evento("deduplicacao", "duplicado_ignorado", "", fonte=fonte.id, item=chave)
                    continue
                tema, pontos = classificar(item)  # decisão 4: tema reconhecido?
                if tema is None:
                    c["sem_tema"] += 1
                    registro.evento("classificacao", "revisar_tema", "nenhuma palavra-chave",
                                    fonte=fonte.id, item=chave, nivel="WARN")
                else:
                    registro.evento("classificacao", tema, f"pontos={pontos[tema]}",
                                    fonte=fonte.id, item=chave)
                rascunho = montar(item, chave, tema).para_dict()
                resultado, msg = entregador.enviar(rascunho)
                if resultado == FALHOU:  # decisão 5: entrega aceita?
                    pend = fila.carregar()
                    pend.append(rascunho)
                    fila.regravar(pend)
                    c["na_fila"] += 1
                    registro.evento("entrega", "fila_reenvio", msg, fonte=fonte.id, item=chave,
                                    nivel="ERROR")
                elif resultado == JA_EXISTIA:
                    c["ja_existiam_no_mvp"] += 1
                    registro.evento("entrega", resultado, msg, fonte=fonte.id, item=chave)
                else:
                    c["rascunhos_entregues"] += 1
                    registro.evento("entrega", ENVIADO, msg, fonte=fonte.id, item=chave)
                vistos.adicionar(chave)
            except Exception as erro:  # nenhum item derruba a execução inteira
                c["erros_inesperados"] += 1
                registro.evento("item", "erro_inesperado", f"{type(erro).__name__}: {erro}",
                                fonte=fonte.id, item=chave, nivel="ERROR")

    # 5. Encerramento
    vistos.salvar()
    resumo = {
        "execucao": execucao_id,
        "modo_entrega": modo,
        "fim": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **{k: c.get(k, 0) for k in (
            "fontes_ok", "fontes_indisponiveis", "fontes_invalidas", "itens_coletados",
            "itens_invalidos", "fora_do_tema", "duplicados", "sem_tema", "rascunhos_entregues",
            "ja_existiam_no_mvp", "na_fila", "reenviados_da_fila", "fila_ainda_pendente",
            "erros_inesperados")},
        "motivos_invalidos": dict(motivos_invalidos),
        "log": registro.arquivo.name,
    }
    (registro.arquivo.parent / f"resumo_{execucao_id}.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    registro.evento("fim", "ok", json.dumps({k: v for k, v in resumo.items()
                                             if isinstance(v, int) and v}, ensure_ascii=False))
    return resumo


def _quarentenar(arquivo: Path, item, motivo: str, execucao_id: str) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    linha = {"execucao": execucao_id, "motivo": motivo, "fonte": item.fonte_id,
             "titulo": sanitizar(item.titulo)[:120], "link": item.link, "data": item.data}
    with arquivo.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
