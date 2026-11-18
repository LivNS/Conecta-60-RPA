"""Regras de negócio: validação, deduplicação e classificação de tema."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from .modelos import Fonte, ItemBruto

# ---------- Validação ----------

IDADE_MAXIMA_DIAS = 180
TOLERANCIA_FUTURO = timedelta(days=1)


def ler_data(texto: str) -> datetime | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    for tentativa in (
        lambda t: datetime.fromisoformat(t.replace("Z", "+00:00")),
        parsedate_to_datetime,
        lambda t: datetime.strptime(t, "%d/%m/%Y"),
    ):
        try:
            data = tentativa(texto)
        except (ValueError, TypeError, IndexError):
            continue
        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)
        return data
    return None


def dominio_permitido(link: str, dominios: list[str]) -> bool:
    host = (urlparse(link).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in dominios)


def validar(item: ItemBruto, fonte: Fonte, agora: datetime | None = None) -> tuple[bool, str]:
    """Retorna (válido, motivo). Motivos são códigos curtos usados nos logs."""
    agora = agora or datetime.now(timezone.utc)
    if len(item.titulo) < 10:
        return False, "titulo_ausente_ou_curto"
    if not item.link:
        return False, "link_ausente"
    if urlparse(item.link).scheme not in ("http", "https"):
        return False, "link_invalido"
    if not dominio_permitido(item.link, fonte.dominios_permitidos):
        return False, "origem_nao_permitida"
    data = ler_data(item.data)
    if data is None:
        return False, "data_invalida"
    if data > agora + TOLERANCIA_FUTURO:
        return False, "data_no_futuro"
    if data < agora - timedelta(days=IDADE_MAXIMA_DIAS):
        return False, "noticia_antiga"
    return True, "ok"


def relevante(item: ItemBruto, fonte: Fonte) -> bool:
    """Fontes gerais (ex.: agência de notícias) só repassam itens sobre golpes."""
    if not fonte.palavras_relevancia:
        return True
    texto = normalizar(f"{item.titulo} {item.resumo}")
    return any(normalizar(p) in texto for p in fonte.palavras_relevancia)


# ---------- Deduplicação ----------

def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


def chave_item(item: ItemBruto) -> str:
    base = normalizar(item.titulo) + "|" + item.link.lower().rstrip("/")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


class Vistos:
    """Memória de itens já processados, persistida entre execuções."""

    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        try:
            self._ids = set(json.loads(arquivo.read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError):
            self._ids = set()

    def contem(self, chave: str) -> bool:
        return chave in self._ids

    def adicionar(self, chave: str) -> None:
        self._ids.add(chave)

    def salvar(self) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps(sorted(self._ids)), encoding="utf-8")


# ---------- Classificação de tema ----------

TEMAS: dict[str, dict] = {
    "banco_falso": {
        "rotulo": "Falso contato do banco",
        "palavras": ["banco", "conta bloqueada", "cartao", "central de atendimento",
                     "gerente", "token", "fatura", "boleto", "phishing"],
    },
    "pix_parente": {
        "rotulo": "Pedido de dinheiro de falso parente",
        "palavras": ["pix", "numero novo", "troquei de numero", "filho", "filha", "neto",
                     "parente", "transferencia", "emprestar dinheiro"],
    },
    "codigo_verificacao": {
        "rotulo": "Pedido de código de verificação",
        "palavras": ["codigo de verificacao", "codigo de seguranca", "codigo por sms",
                     "clonagem", "clonado", "conta de whatsapp", "seis digitos"],
    },
    "falso_suporte": {
        "rotulo": "Falso suporte técnico",
        "palavras": ["suporte", "acesso remoto", "instalar", "instale", "aplicativo falso",
                     "tecnico", "atualizacao de seguranca", "virus"],
    },
    "promocao_falsa": {
        "rotulo": "Falsa promoção ou prêmio",
        "palavras": ["premio", "sorteio", "promocao", "brinde", "voce ganhou", "cupom",
                     "desconto imperdivel", "loja falsa"],
    },
    "inss_beneficios": {
        "rotulo": "Golpe com aposentadoria ou benefício",
        "palavras": ["inss", "aposentadoria", "aposentado", "beneficio", "consignado",
                     "prova de vida", "meu inss", "pensao"],
    },
}


def classificar(item: ItemBruto) -> tuple[str | None, dict[str, int]]:
    """Conta palavras-chave por tema. Sem nenhuma ocorrência, retorna None."""
    texto = normalizar(f"{item.titulo} {item.resumo}")
    pontos = {tema: sum(texto.count(p) for p in cfg["palavras"]) for tema, cfg in TEMAS.items()}
    melhor = max(pontos, key=lambda t: pontos[t])
    if pontos[melhor] == 0:
        return None, pontos
    return melhor, pontos
