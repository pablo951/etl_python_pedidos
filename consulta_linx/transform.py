import time
from math import trunc
from numbers import Integral
from types import SimpleNamespace

import pandas as pd

from . import config
from .utils import cod, log, num, numerico_se_possivel


def preparar_dimensoes(data: dict) -> SimpleNamespace:
    clients = data["cli"].rename(columns={"NOME": "NOME_CLIENTE"}).copy()
    for column in ["CLIENTE", "COD_CLIENTE", "GERADOR"]:
        clients[column] = cod(clients[column])
    clients = clients.drop_duplicates("CLIENTE")

    products = data["prod"].rename(columns={"DESCRICAO1": "DESCRICAO_PRODUTO"}).copy()
    products["PRODUTO"] = cod(products["PRODUTO"])
    products = products.drop_duplicates("PRODUTO")

    addresses = data["end"].copy()
    addresses["GERADOR"] = cod(addresses["GERADOR"])
    cities = addresses.drop_duplicates("GERADOR").set_index("GERADOR")["CIDADE"].to_dict()

    employees = data["func"].copy()
    employees["FUNCIONARIO"] = cod(employees["FUNCIONARIO"])
    salespeople = employees.drop_duplicates("FUNCIONARIO").set_index("FUNCIONARIO")["NOME"].to_dict()

    order_types = data["tipos_pedido"].copy()
    order_types["TIPO_PEDIDO"] = cod(order_types["TIPO_PEDIDO"])
    order_type_descriptions = (
        order_types.drop_duplicates("TIPO_PEDIDO")
        .set_index("TIPO_PEDIDO")["DESCRICAO"]
        .to_dict()
    )

    conditions = set(cod(data["cond"]["CONDICOES_PGTO"]).dropna())
    return SimpleNamespace(
        cli=clients,
        prod=products,
        cidade=cities,
        vendedores=salespeople,
        tipos_pedido=order_type_descriptions,
        conds=conditions,
    )


def montar_vendas(ped: pd.DataFrame, dims, compat: bool) -> pd.DataFrame:
    """Prepara os itens de pedido e aplica as regras de canal."""
    sales = ped.copy()
    acerto_inteiro = sales["ACERTO"].dropna().map(
        lambda value: isinstance(value, Integral)
    ).all()

    for column in [
        "PEDIDOV", "PRODUTO", "CLIENTE", "SAIDA", "CONDICOES_PGTO", "VENDEDOR", "TIPO_PEDIDO",
    ]:
        sales[column] = cod(sales[column])
    for column in ["FILIAL", "QUANTIDADE", "ENTREGUE", "PRECO", "ACERTO"]:
        sales[column] = num(sales[column])
    sales["DATA_PEDIDO"] = pd.to_datetime(sales["DATA_PEDIDO"])

    # O SQL B2B associa a cada pedido todas as saídas registradas em seus itens.
    exit_codes = sales.loc[sales["SAIDA"].notna(), ["PEDIDOV", "SAIDA"]].drop_duplicates()
    sales = sales.drop(columns="SAIDA").merge(exit_codes, on="PEDIDOV", how="left")

    sales = sales.merge(
        dims.prod[["PRODUTO", "COD_PRODUTO", "DESCRICAO_PRODUTO"]],
        on="PRODUTO",
        how="inner",
    )
    sales = sales.merge(
        dims.cli[["CLIENTE", "COD_CLIENTE", "NOME_CLIENTE", "PF_PJ", "UFIE", "GERADOR"]],
        on="CLIENTE",
        how="inner",
    )
    sales = sales[sales["CONDICOES_PGTO"].isin(dims.conds)].copy()

    branch = sales["FILIAL"]
    order_type = sales["TIPO_PEDIDO"]
    is_kiosk = sales["COD_CLIENTE"].fillna("").astype(str).str.contains("C", regex=False)

    channel = pd.Series("", index=sales.index, dtype="object")
    channel = channel.mask(branch == 105, "B2C")
    channel = channel.mask((branch == 105) & (order_type == config.TIPO_PEDIDO_MKT), "MKT")
    channel = channel.mask(branch == 1, "B2B")
    sales["CANAL"] = channel.mask((branch == 1) & is_kiosk, "QUIOSQUE")

    is_valid_customer = (branch != 1) | is_kiosk | sales["PF_PJ"].eq("PJ")

    conditions = sales["CONDICOES_PGTO"]
    excluded_b2b = (
        (sales["VENDEDOR"] == config.VENDEDOR_EXCLUIDO_B2B)
        | conditions.isna()
        | conditions.isin(config.COND_EXCLUIDAS_B2B)
        | (order_type == config.TIPO_PEDIDO_EXCLUIDO_B2B)
        | (
            sales["ORIGEM_PEDIDO"].eq("COPIADO")
            & (sales["DATA_PEDIDO"] == config.DATA_COPIADOS_EXCLUIDOS)
        )
    )
    if compat:
        excluded_b2b = excluded_b2b | sales["VENDEDOR"].isna() | order_type.isna()
    exclude_order = (branch == 1) & ~is_kiosk & excluded_b2b

    sales = sales[is_valid_customer & ~exclude_order].copy()
    sales["CANCELADO"] = sales["QUITA_ITEM"].eq("T")
    sales["QTD_X_PRECO"] = sales["QUANTIDADE"] * sales["PRECO"]
    sales["ENT_X_PRECO"] = sales["ENTREGUE"] * sales["PRECO"]

    grouping_columns = [
        "CANAL", "FILIAL", "PEDIDOV", "COD_PEDIDOV", "DATA_PEDIDO", "APROVADO",
        "CANCELADO", "COD_CLIENTE", "NOME_CLIENTE", "GERADOR", "UFIE", "VENDEDOR",
        "PRODUTO", "COD_PRODUTO", "DESCRICAO_PRODUTO", "SAIDA", "CONDICOES_PGTO",
        "ACERTO", "TIPO_PEDIDO",
    ]
    grouped = sales.groupby(grouping_columns, dropna=False, as_index=False).agg(
        SQ=("QUANTIDADE", "sum"),
        SE=("ENTREGUE", "sum"),
        SQP=("QTD_X_PRECO", "sum"),
        SEP=("ENT_X_PRECO", "sum"),
    )

    use_delivered = grouped["SQ"] == 0
    grouped["QUANTIDADE_PEDIDO"] = grouped["SE"].where(use_delivered, grouped["SQ"])
    base_value = grouped["SEP"].where(use_delivered, grouped["SQP"])

    if compat:
        fraction = grouped["ACERTO"] / 100
        if acerto_inteiro:
            fraction = fraction.map(lambda value: trunc(value) if pd.notna(value) else value)
    else:
        fraction = grouped["ACERTO"].fillna(0) / 100
    factor = (1 + fraction).where(grouped["FILIAL"] == 1, 1.0)
    grouped["VALOR_PEDIDO"] = base_value * factor

    grouped["COD_VENDEDOR"] = (
        grouped["VENDEDOR"].where(grouped["VENDEDOR"].notna(), "-2000000000")
        .replace({"474": "473"})
    )
    grouped["STATUS_APROVACAO"] = (
        pd.Series("APROVADO", index=grouped.index)
        .mask(grouped["APROVADO"].eq("F"), "EM NEGOCIAÇÃO")
        .mask(grouped["CANCELADO"], "CANCELADO")
    )
    return grouped


def preparar_faturamento(fat: pd.DataFrame, dims) -> pd.DataFrame:
    """Normaliza faturamento e associa cadastros de cliente e produto."""
    invoices = fat.copy()
    for column in [
        "NOTA", "PEDIDO", "PRODUTO", "COD_OPERACAO", "CONDICOES_PGTO", "FUNCIONARIO", "CLIENTE",
    ]:
        invoices[column] = cod(invoices[column])
    for column in ["FILIAL", "COD_EVENTO", "QUANTIDADE_NOTA", "VALOR_NOTA"]:
        invoices[column] = num(invoices[column])
    invoices["DATA_NOTA"] = pd.to_datetime(invoices["DATA_NOTA"])
    invoices = invoices.merge(
        dims.cli[["CLIENTE", "COD_CLIENTE", "NOME_CLIENTE", "GERADOR"]],
        on="CLIENTE",
        how="left",
    )
    return invoices.merge(
        dims.prod[["PRODUTO", "COD_PRODUTO", "DESCRICAO_PRODUTO"]],
        on="PRODUTO",
        how="left",
    )


FT_RENOMEAR = {
    "NOTA": "FT_NOTA",
    "DATA_NOTA": "FT_DATA",
    "COD_EVENTO": "FT_EVENTO",
    "CONDICOES_PGTO": "FT_COND",
    "CFOP": "FT_CFOP",
    "VALOR_NOTA": "FT_VALOR",
}


def _formatar_codigo_tipo_pedido(value):
    if pd.isna(value):
        return None
    code = str(value).strip()
    try:
        return f"{int(code):,}".replace(",", ".")
    except ValueError:
        return code


def bloco_com_pedido(vendas: pd.DataFrame, faturamento: pd.DataFrame, dims) -> pd.DataFrame:
    """Monta linhas de pedido com ou sem nota vinculada."""
    parts = []

    b2b_invoices = faturamento[
        (faturamento["FILIAL"] == 1)
        & faturamento["COD_EVENTO"].isin(config.EVENTOS_B2B)
    ]
    b2b_invoices = (
        b2b_invoices.groupby(
            ["COD_OPERACAO", "PRODUTO", "NOTA", "DATA_NOTA", "CONDICOES_PGTO", "COD_EVENTO"],
            dropna=False,
            as_index=False,
        )["VALOR_NOTA"]
        .sum()
        .rename(columns=FT_RENOMEAR)
        .rename(columns={"COD_OPERACAO": "SAIDA"})
    )
    b2b_invoices["FT_CFOP"] = None
    b2b = vendas[vendas["CANAL"] == "B2B"].merge(
        b2b_invoices, on=["SAIDA", "PRODUTO"], how="left"
    )
    b2b = b2b[b2b["FT_NOTA"].isna() | ~b2b["FT_NOTA"].isin(config.NOTAS_EXCL_COM_PEDIDO)]
    parts.append(b2b)

    for channel, events, minimum_date in (
        ("QUIOSQUE", config.EVENTOS_QUIOSQUE, None),
        ("B2C", config.EVENTOS_B2C, None),
        ("MKT", config.EVENTOS_MKT, config.MKT_DATA_MINIMA_NOTA),
    ):
        invoices = faturamento[faturamento["COD_EVENTO"].isin(events)]
        if minimum_date is not None:
            invoices = invoices[invoices["DATA_NOTA"] >= minimum_date]
        invoices = invoices[["PEDIDO", "PRODUTO", *FT_RENOMEAR]].rename(
            columns={**FT_RENOMEAR, "PEDIDO": "PEDIDOV"}
        )
        parts.append(
            vendas[vendas["CANAL"] == channel].merge(
                invoices, on=["PEDIDOV", "PRODUTO"], how="left"
            )
        )

    data = pd.concat(parts, ignore_index=True)
    channel, event, invoice_condition, invoice_cfop = (
        data["CANAL"], data["FT_EVENTO"], data["FT_COND"], data["FT_CFOP"]
    )
    bonus_condition = data["CONDICOES_PGTO"].isin(config.COND_BONIF)
    bonus = (
        channel.isin(["B2B", "QUIOSQUE"])
        & (
            event.isin(config.EVENTOS_BONIF)
            | invoice_condition.isin(config.COND_BONIF)
            | bonus_condition
        )
    ) | (
        (channel == "B2C")
        & (
            event.isin([203])
            | invoice_condition.isin(config.COND_BONIF)
            | bonus_condition
            | invoice_cfop.isin(config.CFOP_BONIF)
        )
    ) | (channel == "MKT")
    order_type = pd.Series("VENDA", index=data.index).mask(bonus, "BONIFICAÇÃO")

    no_invoice = data["FT_NOTA"].isna()
    order_year = pd.to_datetime(data["DATA_PEDIDO"]).dt.year
    order_status = (
        pd.Series("FATURADO", index=data.index)
        .mask(no_invoice, "ABERTO")
        .mask(no_invoice & (order_year <= 2024), "CANCELADO")
        .mask(data["CANCELADO"].astype(bool), "CANCELADO")
    )

    return pd.DataFrame(
        {
            "CANAL": channel,
            "PEDIDO": data["COD_PEDIDOV"],
            "DATA_PEDIDO": data["DATA_PEDIDO"],
            "TIPO_PEDIDO": data["TIPO_PEDIDO"].map(_formatar_codigo_tipo_pedido),
            "DESCRICAO_TIPO_PEDIDO": data["TIPO_PEDIDO"].map(dims.tipos_pedido),
            "CLASSIFICACAO_PEDIDO": order_type,
            "STATUS_APROVACAO": data["STATUS_APROVACAO"],
            "STATUS_PEDIDO": order_status,
            "DATA_FATURAMENTO": data["FT_DATA"],
            "COD_VENDEDOR": data["COD_VENDEDOR"],
            "VENDEDOR": data["COD_VENDEDOR"].map(dims.vendedores),
            "COD_CLIENTE": data["COD_CLIENTE"],
            "CLIENTE": data["NOME_CLIENTE"],
            "CIDADE": data["GERADOR"].map(dims.cidade),
            "ESTADO": data["UFIE"],
            "NF": data["FT_NOTA"],
            "COD_PRODUTO": data["COD_PRODUTO"],
            "PRODUTO": data["DESCRICAO_PRODUTO"],
            "QUANTIDADE": data["QUANTIDADE_PEDIDO"],
            "VALOR_PEDIDO": data["VALOR_PEDIDO"],
            "VALOR_NF": data["FT_VALOR"],
        }
    )


def bloco_sem_pedido(faturamento: pd.DataFrame, dims, linked_exits: set | None) -> pd.DataFrame:
    """Monta linhas de notas fiscais sem pedido vinculado."""
    invoices = faturamento[faturamento["PEDIDO"].isna()]
    b2b_without_order = True
    if linked_exits is not None:
        b2b_without_order = ~invoices["COD_OPERACAO"].isin(linked_exits)

    is_b2b = (
        (invoices["FILIAL"] == 1)
        & b2b_without_order
        & invoices["COD_EVENTO"].isin(config.EVENTOS_B2B)
        & (
            (invoices["FUNCIONARIO"] != config.VENDEDOR_EXCLUIDO_B2B)
            | invoices["FUNCIONARIO"].isna()
        )
        & ~invoices["NOTA"].isin(config.NOTAS_EXCL_SEM_PEDIDO)
    )
    is_b2c = (invoices["FILIAL"] == 105) & invoices["COD_EVENTO"].isin(config.EVENTOS_B2C)
    invoices = invoices[is_b2b | is_b2c].copy()

    b2b = invoices["FILIAL"] == 1
    bonus_cfop = invoices["CFOP"].isin(config.CFOP_BONIF)
    bonus = bonus_cfop.where(
        b2b,
        invoices["COD_EVENTO"].isin([203])
        | invoices["CONDICOES_PGTO"].isin(config.COND_BONIF)
        | bonus_cfop,
    )
    order_type = pd.Series("VENDA", index=invoices.index).mask(bonus, "BONIFICAÇÃO")
    salesperson_code = (
        invoices["FUNCIONARIO"].where(invoices["FUNCIONARIO"].notna(), "-2000000000")
        .replace({"474": "473"})
        .where(b2b, None)
    )
    return pd.DataFrame(
        {
            "CANAL": b2b.map({True: "B2B", False: "B2C"}),
            "PEDIDO": None,
            "DATA_PEDIDO": invoices["DATA_NOTA"].where(b2b),
            "TIPO_PEDIDO": None,
            "DESCRICAO_TIPO_PEDIDO": None,
            "CLASSIFICACAO_PEDIDO": order_type,
            "STATUS_APROVACAO": "APROVADO",
            "STATUS_PEDIDO": "FATURADO",
            "DATA_FATURAMENTO": invoices["DATA_NOTA"],
            "COD_VENDEDOR": salesperson_code,
            "VENDEDOR": salesperson_code.map(dims.vendedores),
            "COD_CLIENTE": invoices["COD_CLIENTE"],
            "CLIENTE": invoices["NOME_CLIENTE"],
            "CIDADE": invoices["GERADOR"].map(dims.cidade),
            "ESTADO": invoices["ESTADO"],
            "NF": invoices["NOTA"],
            "COD_PRODUTO": invoices["COD_PRODUTO"],
            "PRODUTO": invoices["DESCRICAO_PRODUTO"],
            "QUANTIDADE": invoices["QUANTIDADE_NOTA"],
            "VALOR_PEDIDO": float("nan"),
            "VALOR_NF": invoices["VALOR_NOTA"],
        }
    )


def transformar(data: dict, compat: bool) -> pd.DataFrame:
    started = time.time()
    dimensions = preparar_dimensoes(data)
    sales = montar_vendas(data["ped"], dimensions, compat)
    invoices = preparar_faturamento(data["fat"], dimensions)

    linked_exits = None
    if not compat and "saidas" in data:
        linked_exits = set(cod(data["saidas"]["SAIDA"]).dropna())
    result = pd.concat(
        [
            bloco_com_pedido(sales, invoices, dimensions),
            bloco_sem_pedido(invoices, dimensions, linked_exits),
        ],
        ignore_index=True,
    )

    valid = (
        ~result["CANAL"].isin(["B2C", "MKT"])
        | (
            (result["STATUS_APROVACAO"] == "APROVADO")
            & (result["STATUS_PEDIDO"] == "FATURADO")
        )
    )
    result = result[valid]

    for column in ["PEDIDO", "NF", "COD_VENDEDOR"]:
        result[column] = numerico_se_possivel(result[column])
    for column in ["DATA_PEDIDO", "DATA_FATURAMENTO"]:
        result[column] = pd.to_datetime(result[column])

    result = (
        result[config.COLUNAS_SAIDA]
        .sort_values(["CANAL", "DATA_PEDIDO", "PEDIDO", "NF"], na_position="last")
        .reset_index(drop=True)
    )
    log(f"Regras aplicadas: {len(result):,} linhas em {time.time() - started:.1f}s")
    return result