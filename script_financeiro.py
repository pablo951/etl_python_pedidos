#!/usr/bin/env python3
"""Gera os títulos a receber por cliente (nota, pedido, vendedor, devolução e pagamento)."""

import sys
import time

from consulta_linx import config, financeiro
from consulta_linx.database import conectar
from consulta_linx.parquet import caminho_parquet, salvar_parquet
from consulta_linx.utils import log, log_erro


def main() -> int:
    started = time.time()
    log(f"Financeiro: títulos emitidos a partir de {config.FINANCEIRO_DATA_INICIAL}")
    try:
        connection = conectar()
    except Exception:
        log_erro(
            f"ERRO ao conectar no Firebird "
            f"({config.FB_HOST}:{config.FB_PORT}/{config.FB_DATABASE})"
        )
        return 1

    try:
        data = financeiro.extrair(connection, config.FINANCEIRO_DATA_INICIAL)
    except Exception:
        log_erro("ERRO na extração do financeiro")
        return 2
    finally:
        connection.close()

    try:
        titulos = financeiro.transformar(data)
        resumo = financeiro.resumo_por_cliente(titulos)
    except Exception:
        log_erro("ERRO ao montar os títulos")
        return 3

    output_path = config.ARQUIVO_SAIDA_FINANCEIRO
    try:
        output_file = financeiro.salvar_excel(titulos, resumo, output_path)
    except Exception:
        log_erro(f"ERRO ao salvar o Excel em {output_path}")
        return 4

    parquet_path = caminho_parquet(output_path)
    try:
        parquet_file = salvar_parquet(titulos, parquet_path, financeiro.SCHEMA_TITULOS)
    except Exception:
        log_erro(f"ERRO ao salvar o Parquet em {parquet_path}")
        return 5
    log(
        f"Pronto: {output_file.resolve()} | {parquet_file.resolve()} "
        f"({len(titulos):,} títulos, {len(resumo):,} clientes, {time.time() - started:.1f}s no total)"
    )
    print(titulos["SITUACAO"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
