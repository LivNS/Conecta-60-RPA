"""Uso: python -m rpa_alertas [--config config/fontes.json] [--silencioso]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .modelos import ConfiguracaoInvalida
from .robo import executar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rpa_alertas",
                                description="Robô de alertas educativos sobre golpes digitais")
    p.add_argument("--config", default="config/fontes.json", type=Path)
    p.add_argument("--silencioso", action="store_true", help="não ecoa o log no terminal")
    args = p.parse_args(argv)
    try:
        resumo = executar(args.config, ecoar=not args.silencioso)
    except ConfiguracaoInvalida as erro:
        print(f"ERRO de configuração: {erro}", file=sys.stderr)
        return 2
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    # código 1 sinaliza ao agendador que algo precisa de atenção (sem esconder falhas)
    atencao = resumo["fontes_indisponiveis"] + resumo["fontes_invalidas"] + resumo["na_fila"] \
        + resumo["erros_inesperados"]
    return 1 if atencao else 0


if __name__ == "__main__":
    sys.exit(main())
