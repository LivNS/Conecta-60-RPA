"""Monta o rascunho educativo, em linguagem simples, a partir de um item validado."""
from __future__ import annotations

import html
import re

from .modelos import ItemBruto, Rascunho
from .regras import TEMAS, ler_data

DICAS = {
    "banco_falso": [
        "O banco não pede senha, código ou token por mensagem ou ligação.",
        "Não clique no link. Abra o aplicativo do banco você mesmo.",
        "Na dúvida, ligue para o número que está atrás do seu cartão.",
    ],
    "pix_parente": [
        "Desconfie de \"troquei de número\" com pedido de dinheiro.",
        "Ligue para o número antigo da pessoa antes de fazer qualquer Pix.",
        "Combine com a família uma palavra-senha para emergências.",
    ],
    "codigo_verificacao": [
        "Nunca passe códigos que chegam por SMS ou WhatsApp, para ninguém.",
        "Quem pede esse código quer entrar na sua conta.",
        "Ative a verificação em duas etapas do WhatsApp.",
    ],
    "falso_suporte": [
        "Não instale aplicativos pedidos por desconhecidos.",
        "Empresas sérias não pedem acesso remoto ao seu celular.",
        "Desligue a ligação e procure o canal oficial da empresa.",
    ],
    "promocao_falsa": [
        "Prêmio que você não pediu costuma ser isca.",
        "Não pague taxa para receber prêmio.",
        "Confira a promoção no site oficial da loja, digitando o endereço.",
    ],
    "inss_beneficios": [
        "O INSS não liga nem manda link pedindo dados ou pagamento.",
        "Consulte seu benefício só pelo aplicativo Meu INSS ou pelo telefone 135.",
        "Desconfie de ofertas de empréstimo consignado que chegam sem você pedir.",
    ],
    None: [
        "Desconfie de pressa, ameaça ou oferta boa demais.",
        "Não clique em links nem passe dados pessoais por mensagem.",
        "Confirme sempre pelo canal oficial, buscado por você.",
    ],
}

LIMITE_RESUMO = 280


def limpar(texto: str) -> str:
    texto = html.unescape(re.sub(r"<[^>]+>", " ", texto or ""))
    return re.sub(r"\s+", " ", texto).strip()


def resumir(texto: str, limite: int = LIMITE_RESUMO) -> str:
    texto = limpar(texto)
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(".,;:") + "…"


def montar(item: ItemBruto, chave: str, tema: str | None) -> Rascunho:
    data = ler_data(item.data)
    resumo = resumir(item.resumo) or "Leia o aviso completo na fonte original."
    return Rascunho(
        id=chave,
        titulo=limpar(item.titulo),
        tema=tema or "revisar_tema",
        tema_rotulo=TEMAS[tema]["rotulo"] if tema else "Tema a definir na revisão",
        resumo_simples=resumo,
        como_se_proteger=DICAS[tema],
        fonte_nome=item.fonte_nome,
        link_fonte=item.link,
        data_publicacao=data.date().isoformat() if data else "",
        precisa_revisar_tema=tema is None,
    )
