from pathlib import Path

import pandas as pd
import pyarrow as pa

from . import config
from .utils import substituir_arquivo


def montar_schema(colunas: list[str], texto: list[str], data: list[str], inteiro=()) -> pa.Schema:
    """string (não large_string), que o conector Parquet do Power BI lê sem problemas."""
    return pa.schema(
        [
            (
                column,
                pa.string() if column in texto
                else pa.timestamp("ms") if column in data
                else pa.int64() if column in inteiro
                else pa.float64(),
            )
            for column in colunas
        ]
    )


# Códigos ficam como texto para o schema não mudar entre execuções
# (numerico_se_possivel pode devolver Int64 ou object) e para preservar zeros à esquerda.
SCHEMA_PEDIDOS = montar_schema(
    config.COLUNAS_SAIDA,
    texto=[
        "CANAL", "PEDIDO", "TIPO_PEDIDO", "DESCRICAO_TIPO_PEDIDO", "CLASSIFICACAO_PEDIDO",
        "STATUS_APROVACAO", "STATUS_PEDIDO", "COD_VENDEDOR", "VENDEDOR", "COD_CLIENTE",
        "CLIENTE", "CIDADE", "ESTADO", "NF", "COD_PRODUTO", "PRODUTO",
    ],
    data=["DATA_PEDIDO", "DATA_FATURAMENTO", "DATA_HORA_EMISSAO", "DATA_HORA_REGISTRO"],
)


def preparar_tipos(result: pd.DataFrame, schema: pa.Schema) -> pd.DataFrame:
    data = result[schema.names].copy()
    for field in schema:
        column = field.name
        if pa.types.is_string(field.type):
            data[column] = data[column].astype("string")
        elif pa.types.is_timestamp(field.type):
            data[column] = pd.to_datetime(data[column]).astype("datetime64[ms]")
        elif pa.types.is_integer(field.type):
            data[column] = pd.to_numeric(data[column], errors="coerce").astype("Int64")
        else:
            data[column] = pd.to_numeric(data[column], errors="coerce").astype("float64")
    return data


def caminho_parquet(arquivo_excel: Path) -> Path:
    return config.PASTA_SAIDA_PARQUET / f"{arquivo_excel.stem}.parquet"


def salvar_parquet(result: pd.DataFrame, destino: Path, schema: pa.Schema = SCHEMA_PEDIDOS) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = destino.with_name(destino.stem + ".tmp.parquet")
    preparar_tipos(result, schema).to_parquet(
        temporary_file, engine="pyarrow", schema=schema, compression="snappy", index=False
    )
    return substituir_arquivo(temporary_file, destino)
