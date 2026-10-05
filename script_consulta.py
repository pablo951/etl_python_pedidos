#!/usr/bin/env python3
"""Executa a consulta de pedidos e exporta o relatório consolidado."""

import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from consulta_linx import config
from consulta_linx.database import conectar, extrair
from consulta_linx.excel import resumo_por_canal, salvar_excel
from consulta_linx.transform import transformar
from consulta_linx.utils import log, log_erro


def executar_consulta(
    start_date: datetime,
    end_date: datetime,
    output_path: Path,
) -> int:
    log(
        f"Janela: {start_date:%d/%m/%Y} até {(end_date - timedelta(days=1)):%d/%m/%Y} "
        f"| modo compatível: {config.MODO_COMPATIVEL}"
    )

    started = time.time()
    try:
        connection = conectar()
    except Exception:
        log_erro(
            f"ERRO ao conectar no Firebird "
            f"({config.FB_HOST}:{config.FB_PORT}/{config.FB_DATABASE})"
        )
        return 1

    try:
        data = extrair(
            connection,
            start_date,
            end_date,
            config.MODO_COMPATIVEL,
        )
    except Exception:
        log_erro("ERRO na extração")
        return 2
    finally:
        connection.close()

    try:
        result = transformar(data, config.MODO_COMPATIVEL)
    except Exception:
        log_erro("ERRO ao aplicar as regras de negócio")
        return 3

    try:
        output_file = salvar_excel(
            result,
            output_path,
            start_date,
            end_date,
            config.MODO_COMPATIVEL,
        )
    except Exception:
        log_erro(f"ERRO ao salvar o Excel em {output_path}")
        return 4
    log(
        f"Pronto: {output_file.resolve()} "
        f"({len(result):,} linhas, {time.time() - started:.1f}s no total)"
    )
    print(resumo_por_canal(result).to_string(index=False))
    return 0


def main() -> int:
    today = date.today()
    start_date = datetime.combine(
        today - timedelta(days=config.DIAS_JANELA), datetime.min.time()
    )
    end_date = datetime.combine(today + timedelta(days=1), datetime.min.time())
    return executar_consulta(start_date, end_date, config.ARQUIVO_SAIDA)


if __name__ == "__main__":
    sys.exit(main())
