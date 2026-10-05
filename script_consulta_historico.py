#!/usr/bin/env python3
"""Gera o relatório histórico de pedidos desde dezembro de 2023."""

import sys
from datetime import date, datetime, time, timedelta

from consulta_linx import config
from script_consulta import executar_consulta


DATA_INICIAL = date(2023, 12, 1)


def periodo_historico(data_final: date | None = None) -> tuple[datetime, datetime]:
    ultimo_dia = data_final or date.today()
    inicio = datetime.combine(DATA_INICIAL, time.min)
    fim = datetime.combine(ultimo_dia + timedelta(days=1), time.min)
    return inicio, fim


def main() -> int:
    inicio, fim = periodo_historico()
    return executar_consulta(inicio, fim, config.ARQUIVO_SAIDA_HISTORICO)


if __name__ == "__main__":
    sys.exit(main())