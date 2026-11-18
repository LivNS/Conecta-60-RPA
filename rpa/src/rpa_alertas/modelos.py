"""Estruturas de dados do robô de alertas."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


class FonteIndisponivel(Exception):
    """A fonte não respondeu (fora do ar, timeout, arquivo ausente)."""


class FonteInvalida(Exception):
    """A fonte respondeu, mas o conteúdo não pôde ser lido (formato corrompido)."""


class ConfiguracaoInvalida(Exception):
    """O arquivo de configuração está ausente ou incompleto."""


@dataclass
class Fonte:
    id: str
    nome: str
    tipo: str  # "rss" ou "arquivo"
    local: str  # URL (rss) ou pasta (arquivo)
    dominios_permitidos: list[str]
    ativa: bool = True
    # se preenchido, o item só segue se título ou resumo citar ao menos uma destas palavras
    palavras_relevancia: list[str] = field(default_factory=list)


@dataclass
class ItemBruto:
    titulo: str
    link: str
    data: str
    resumo: str
    fonte_id: str
    fonte_nome: str


@dataclass
class Rascunho:
    id: str
    titulo: str
    tema: str
    tema_rotulo: str
    resumo_simples: str
    como_se_proteger: list[str]
    fonte_nome: str
    link_fonte: str
    data_publicacao: str
    precisa_revisar_tema: bool
    status: str = "pendente_revisao"
    origem: str = "rpa"
    criado_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def para_dict(self) -> dict:
        return asdict(self)
