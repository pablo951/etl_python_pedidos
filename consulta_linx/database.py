import time
from datetime import datetime
from numbers import Integral, Real
from decimal import Decimal

import firebirdsql
import pandas as pd

from . import config
from .utils import _cod, limpar, log


def _lista(values) -> str:
    return ", ".join(str(int(value)) for value in values)


def _literal(value) -> str:
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, (Real, Decimal)) and value == int(value):
        return str(int(value))
    return "'" + str(value).replace("'", "''") + "'"


def sql_faturamento(compat: bool) -> str:
    def column(name):
        return f"PE.{name}" if compat else f"COALESCE(PE.{name}, 0)"

    return f"""
SELECT
    NF.FILIAL,
    S.EVENTO              AS COD_EVENTO,
    PE.NOTA,
    PE.PEDIDO,
    CAST(PE.DATA AS DATE) AS DATA_NOTA,
    PE.PRODUTO,
    PE.COD_OPERACAO,
    M.CONDICOES_PGTO,
    M.FUNCIONARIO,
    M.CLIENTE,
    NF.ESTADO,
    CFOP.NAT_OPERACAO     AS CFOP,
    SUM(PE.QUANTIDADE)    AS QUANTIDADE_NOTA,
    SUM(PE.PRECO_APLICADO * PE.QUANTIDADE
        + {column('IT_VALOR_FRETE')}
        + {column('IT_DESP_ACESSORIAS')}
        + {column('V_ICMSS')}
        + {column('V_FCPST')}
        + {column('V_IPI')}
        + {column('IT_VALOR_DESCONTO')}
        - {column('DESC_SUFRAMA')}) AS VALOR_NOTA
FROM PRODUTOS_EVENTOS PE
INNER JOIN NF
        ON NF.NOTA = PE.NOTA
       AND NF.COD_OPERACAO = PE.COD_OPERACAO
       AND NF.TIPO_OPERACAO = 'S'
       AND NF.CANCELADA = 'F'
       AND NF.FILIAL IN (1, 105)
INNER JOIN SAIDAS S     ON S.SAIDA = PE.COD_OPERACAO
INNER JOIN MOVIMENTO M  ON M.COD_OPERACAO = PE.COD_OPERACAO
LEFT JOIN CFOP          ON CFOP.CFOP = PE.CFOP
WHERE PE.DATA >= ? AND PE.DATA < ?
  AND S.EVENTO IN ({_lista(config.EVENTOS_TODOS)})
GROUP BY
    NF.FILIAL, S.EVENTO, PE.NOTA, PE.PEDIDO, CAST(PE.DATA AS DATE), PE.PRODUTO,
    PE.COD_OPERACAO, M.CONDICOES_PGTO, M.FUNCIONARIO, M.CLIENTE, NF.ESTADO,
    CFOP.NAT_OPERACAO
"""


SQL_ITENS_PEDIDO = """
SELECT
    PV.FILIAL,
    PV.PEDIDOV,
    PV.COD_PEDIDOV,
    CAST(PV.DATA_EMISSAO AS DATE) AS DATA_PEDIDO,
    PV.TIPO_PEDIDO,
    PV.ORIGEM_PEDIDO,
    PV.APROVADO,
    PV.VENDEDOR,
    PV.CLIENTE,
    PV.CONDICOES_PGTO,
    PV.ACERTO,
    PPV.PRODUTO,
    PPV.SAIDA,
    PPV.QUANTIDADE,
    PPV.ENTREGUE,
    PPV.PRECO,
    PPV.EMBALADO,
    PPV.QUITA_ITEM
FROM PEDIDO_VENDA PV
INNER JOIN PRODUTO_PEDIDOV PPV ON PPV.PEDIDOV = PV.PEDIDOV
WHERE PV.FILIAL IN (1, 105)
  AND PV.DATA_EMISSAO >= ? AND PV.DATA_EMISSAO < ?
"""

SQL_CLIENTES = """
SELECT CLIENTE, COD_CLIENTE, NOME, PF_PJ, UFIE, GERADOR
FROM CLIENTES WHERE CLIENTE IN ({ids})
"""
SQL_ENDERECOS = """
SELECT GERADOR, CIDADE
FROM ENDERECOS_CADASTRO WHERE ENDERECO_NOTA = 'T' AND GERADOR IN ({ids})
"""
SQL_PRODUTOS = """
SELECT PRODUTO, COD_PRODUTO, DESCRICAO1
FROM PRODUTOS WHERE PRODUTO IN ({ids})
"""
SQL_SAIDAS_VINCULADAS = """
SELECT DISTINCT SAIDA
FROM PRODUTO_PEDIDOV WHERE SAIDA IN ({ids})
"""
SQL_FUNCIONARIOS = "SELECT FUNCIONARIO, NOME FROM FUNCIONARIOS"
SQL_CONDICOES = "SELECT CONDICOES_PGTO FROM CONDICOES_PGTO"
SQL_TIPOS_PEDIDO = """
SELECT TIPO_PEDIDO, DESCRICAO
FROM TIPOS_PEDIDO WHERE TIPO_PEDIDO IN ({ids})
"""


def conectar():
    if not config.FB_DATABASE:
        raise ValueError("Defina FB_DATABASE no arquivo .env")
    return firebirdsql.connect(
        host=config.FB_HOST,
        database=config.FB_DATABASE,
        port=config.FB_PORT,
        user=config.FB_USUARIO,
        password=config.FB_SENHA,
        charset=config.FB_CHARSET,
    )


def consultar(connection, sql: str, params=(), label: str = "") -> pd.DataFrame:
    started = time.time()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        columns = [description[0].strip() for description in cursor.description]
        rows = cursor.fetchall()
    finally:
        cursor.close()
    dataframe = limpar(pd.DataFrame(rows, columns=columns))
    log(f"{label}: {len(dataframe):,} linhas em {time.time() - started:.1f}s")
    return dataframe


def consultar_por_ids(connection, sql_template: str, ids, label: str, batch_size: int = 1000):
    """Executa consultas IN em lotes menores que o limite do Firebird."""
    ids = [value for value in pd.unique(pd.Series(list(ids), dtype=object)) if _cod(value) is not None]
    parts = []
    started = time.time()
    for offset in range(0, len(ids), batch_size):
        values = ", ".join(_literal(value) for value in ids[offset:offset + batch_size])
        cursor = connection.cursor()
        try:
            cursor.execute(sql_template.format(ids=values))
            columns = [description[0].strip() for description in cursor.description]
            parts.append(pd.DataFrame(cursor.fetchall(), columns=columns))
        finally:
            cursor.close()
    if parts:
        dataframe = limpar(pd.concat(parts, ignore_index=True))
    else:
        columns = [name.strip() for name in sql_template.split("SELECT")[1].split("FROM")[0].split(",")]
        dataframe = pd.DataFrame(columns=columns)
    log(f"{label}: {len(dataframe):,} linhas em {time.time() - started:.1f}s")
    return dataframe


def extrair(connection, inicio: datetime, fim: datetime, compat: bool) -> dict:
    data = {
        "fat": consultar(connection, sql_faturamento(compat), (inicio, fim), "Faturamento"),
        "ped": consultar(connection, SQL_ITENS_PEDIDO, (inicio, fim), "Itens de pedido"),
        "func": consultar(connection, SQL_FUNCIONARIOS, (), "Funcionários"),
        "cond": consultar(connection, SQL_CONDICOES, (), "Condições de pagamento"),
    }
    data["tipos_pedido"] = consultar_por_ids(
        connection,
        SQL_TIPOS_PEDIDO,
        data["ped"]["TIPO_PEDIDO"],
        "Tipos de pedido",
    )
    client_ids = list(data["ped"]["CLIENTE"]) + list(data["fat"]["CLIENTE"])
    product_ids = list(data["ped"]["PRODUTO"]) + list(data["fat"]["PRODUTO"])
    data["cli"] = consultar_por_ids(connection, SQL_CLIENTES, client_ids, "Clientes")
    data["prod"] = consultar_por_ids(connection, SQL_PRODUTOS, product_ids, "Produtos")
    data["end"] = consultar_por_ids(connection, SQL_ENDERECOS, data["cli"]["GERADOR"], "Endereços")
    operation_ids = data["fat"].loc[data["fat"]["FILIAL"] == 1, "COD_OPERACAO"]
    data["saidas"] = consultar_por_ids(
        connection, SQL_SAIDAS_VINCULADAS, operation_ids, "Saídas vinculadas"
    )
    return data