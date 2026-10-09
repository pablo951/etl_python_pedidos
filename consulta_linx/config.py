import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

FB_HOST = os.getenv("FB_HOST", "localhost")
FB_DATABASE = os.getenv("FB_DATABASE", "")
FB_PORT = int(os.getenv("FB_PORT", "3050"))
FB_USUARIO = os.getenv("FB_USER", "SYSDBA")
FB_SENHA = os.getenv("FB_PASSWORD", "")
FB_CHARSET = os.getenv("FB_CHARSET", "WIN1252")

DIAS_JANELA = int(os.getenv("DIAS_JANELA", "45"))
PASTA_SAIDA_EXCEL = Path(os.getenv("PASTA_SAIDA_EXCEL", ".")).expanduser()


def _caminho_saida(variavel: str, nome_padrao: str) -> Path:
    caminho = Path(os.getenv(variavel, nome_padrao)).expanduser()
    return caminho if caminho.is_absolute() else PASTA_SAIDA_EXCEL / caminho


ARQUIVO_SAIDA = _caminho_saida("ARQUIVO_SAIDA", "pedidos_unificado.xlsx")
ARQUIVO_SAIDA_HISTORICO = _caminho_saida(
    "ARQUIVO_SAIDA_HISTORICO", "pedidos_unificado_historico.xlsx"
)
# Parquet para o Power BI, em pasta separada dos Excel. Relativo = dentro de PASTA_SAIDA_EXCEL.
PASTA_SAIDA_PARQUET = Path(os.getenv("PASTA_SAIDA_PARQUET") or "parquet").expanduser()
if not PASTA_SAIDA_PARQUET.is_absolute():
    PASTA_SAIDA_PARQUET = PASTA_SAIDA_EXCEL / PASTA_SAIDA_PARQUET
MODO_COMPATIVEL = os.getenv("MODO_COMPATIVEL", "false").strip().lower() in {
    "1", "true", "yes", "sim", "on",
}
ARQUIVO_LOG = Path(os.getenv("ARQUIVO_LOG", "logs/consulta_linx.log"))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
# Se o Excel de saída estiver aberto (ex.: BI atualizando), tenta de novo antes
# de desistir e salvar com outro nome.
SALVAR_TENTATIVAS = int(os.getenv("SALVAR_TENTATIVAS", "5"))
SALVAR_ESPERA_SEG = int(os.getenv("SALVAR_ESPERA_SEG", "60"))

EVENTOS_BONIF = [313, 8, 307, 166, 147, 119, 154, 203, 1, 316]
EVENTOS_B2B = EVENTOS_BONIF + [
    207, 741, 14, 9, 104, 105, 118, 306, 301, 308, 167, 305, 103,
    306714288, 321, 322,
]
EVENTOS_QUIOSQUE = EVENTOS_B2B + [324, 325, 329]
EVENTOS_B2C = [201, 28, 203]
EVENTOS_MKT = [203]
EVENTOS_TODOS = sorted(set(EVENTOS_QUIOSQUE + EVENTOS_B2C))

COND_BONIF = {"8", "40596"}
COND_EXCLUIDAS_B2B = {"9", "51"}
CFOP_BONIF = {"6.910", "5.910"}
VENDEDOR_EXCLUIDO_B2B = "453"
TIPO_PEDIDO_MKT = "20210"
TIPO_PEDIDO_EXCLUIDO_B2B = "20211"
DATA_COPIADOS_EXCLUIDOS = pd.Timestamp("2025-10-21")
MKT_DATA_MINIMA_NOTA = pd.Timestamp("2026-07-01")

NOTAS_EXCL_COM_PEDIDO = {
    "89236", "91873", "94163", "87158", "87169", "89782",
    "89448", "88390", "88702", "93918", "93392", "93345",
}
NOTAS_EXCL_SEM_PEDIDO = NOTAS_EXCL_COM_PEDIDO | {"3997682", "4194080"}

COLUNAS_SAIDA = [
    "CANAL", "PEDIDO", "DATA_PEDIDO", "TIPO_PEDIDO", "DESCRICAO_TIPO_PEDIDO",
    "CLASSIFICACAO_PEDIDO", "STATUS_APROVACAO",
    "STATUS_PEDIDO", "DATA_FATURAMENTO", "DATA_HORA_EMISSAO", "DATA_HORA_REGISTRO",
    "COD_VENDEDOR", "VENDEDOR",
    "COD_CLIENTE", "CLIENTE", "CIDADE", "ESTADO", "NF", "COD_PRODUTO",
    "PRODUTO", "QUANTIDADE", "VALOR_PEDIDO", "VALOR_NF",
]