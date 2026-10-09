import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa

from . import config
from .utils import log

# Códigos ficam como texto para o schema não mudar entre execuções
# (numerico_se_possivel pode devolver Int64 ou object) e para preservar zeros à esquerda.
COLUNAS_TEXTO = [
    "CANAL", "PEDIDO", "TIPO_PEDIDO", "DESCRICAO_TIPO_PEDIDO", "CLASSIFICACAO_PEDIDO",
    "STATUS_APROVACAO", "STATUS_PEDIDO", "COD_VENDEDOR", "VENDEDOR", "COD_CLIENTE",
    "CLIENTE", "CIDADE", "ESTADO", "NF", "COD_PRODUTO", "PRODUTO",
]
COLUNAS_DATA = ["DATA_PEDIDO", "DATA_FATURAMENTO", "DATA_HORA_EMISSAO", "DATA_HORA_REGISTRO"]
COLUNAS_NUMERO = ["QUANTIDADE", "VALOR_PEDIDO", "VALOR_NF"]

# Schema fixo: string (não large_string), que o conector Parquet do Power BI lê sem problemas.
SCHEMA = pa.schema(
    [
        (
            column,
            pa.string() if column in COLUNAS_TEXTO
            else pa.timestamp("ms") if column in COLUNAS_DATA
            else pa.float64(),
        )
        for column in config.COLUNAS_SAIDA
    ]
)


def preparar_tipos(result: pd.DataFrame) -> pd.DataFrame:
    data = result.copy()
    for column in COLUNAS_TEXTO:
        data[column] = data[column].astype("string")
    for column in COLUNAS_DATA:
        data[column] = pd.to_datetime(data[column]).astype("datetime64[ms]")
    for column in COLUNAS_NUMERO:
        data[column] = pd.to_numeric(data[column], errors="coerce").astype("float64")
    return data


def caminho_parquet(arquivo_excel: Path) -> Path:
    return config.PASTA_SAIDA_PARQUET / f"{arquivo_excel.stem}.parquet"


def salvar_parquet(result: pd.DataFrame, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = destino.with_name(destino.stem + ".tmp.parquet")
    preparar_tipos(result).to_parquet(
        temporary_file, engine="pyarrow", schema=SCHEMA, compression="snappy", index=False
    )

    tentativas = max(config.SALVAR_TENTATIVAS, 1)
    for tentativa in range(1, tentativas + 1):
        try:
            temporary_file.replace(destino)
            return destino
        except PermissionError:
            if tentativa < tentativas:
                log(
                    f"'{destino.name}' está em uso (tentativa {tentativa}/{tentativas}); "
                    f"nova tentativa em {config.SALVAR_ESPERA_SEG}s"
                )
                time.sleep(config.SALVAR_ESPERA_SEG)

    alternate = destino.with_name(f"{destino.stem}_{datetime.now():%Y%m%d_%H%M%S}.parquet")
    temporary_file.replace(alternate)
    log(
        f"ATENÇÃO: '{destino.name}' continuou em uso; salvei como '{alternate.name}'. "
        f"O BI ainda está lendo a versão anterior."
    )
    return alternate
