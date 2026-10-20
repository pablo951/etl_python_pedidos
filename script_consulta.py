#!/usr/bin/env python3
"""Executa a consulta de pedidos e exporta o relatório consolidado."""

import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from consulta_linx import config
from consulta_linx.database import conectar, extrair
from consulta_linx.excel import resumo_por_canal, salvar_excel
from consulta_linx.parquet import (
    caminho_parquet,
    data_referencia,
    salvar_parquet,
    salvar_parquet_mensal,
)
from consulta_linx.transform import transformar
from consulta_linx.utils import log, log_erro


def executar_consulta(
    start_date: datetime,
    end_date: datetime,
    output_path: Path,
) -> int:
    # Extrai desde o dia 1 do mês para regravar os Parquet mensais completos;
    # o Excel e o Parquet do período continuam só com a janela pedida.
    extraction_start = start_date.replace(day=1)
    log(
        f"Janela: {start_date:%d/%m/%Y} até {(end_date - timedelta(days=1)):%d/%m/%Y} "
        f"(extração desde {extraction_start:%d/%m/%Y}) "
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
            extraction_start,
            end_date,
            config.MODO_COMPATIVEL,
        )
    except Exception:
        log_erro("ERRO na extração")
        return 2
    finally:
        connection.close()

    try:
        full_result = transformar(data, config.MODO_COMPATIVEL)
    except Exception:
        log_erro("ERRO ao aplicar as regras de negócio")
        return 3
    result = full_result[data_referencia(full_result) >= start_date].reset_index(drop=True)

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

    parquet_path = caminho_parquet(output_path)
    try:
        parquet_file = salvar_parquet(result, parquet_path)
    except Exception:
        log_erro(f"ERRO ao salvar o Parquet em {parquet_path}")
        return 5

    try:
        monthly_files = salvar_parquet_mensal(full_result, extraction_start, end_date)
    except Exception:
        log_erro(f"ERRO ao salvar os Parquet mensais em {config.PASTA_PARQUET_MENSAL}")
        return 6
    log(
        f"Parquet mensais: {monthly_files[0].name} a {monthly_files[-1].name} "
        f"em {config.PASTA_PARQUET_MENSAL.resolve()}"
    )
    log(
        f"Pronto: {output_file.resolve()} | {parquet_file.resolve()} "
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
