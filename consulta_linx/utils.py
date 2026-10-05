from datetime import datetime
from decimal import Decimal
import logging
from logging.handlers import RotatingFileHandler
from numbers import Real
import sys

import pandas as pd

from . import config

_logger = logging.getLogger("consulta_linx")


def _get_logger() -> logging.Logger:
    if not _logger.handlers:
        config.ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")

        file_handler = RotatingFileHandler(
            config.ARQUIVO_LOG,
            maxBytes=config.LOG_MAX_BYTES,
            backupCount=config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        _logger.setLevel(logging.INFO)
        _logger.propagate = False
        _logger.addHandler(file_handler)
        _logger.addHandler(console_handler)
    return _logger


def log(message: str) -> None:
    _get_logger().info(message)


def log_erro(message: str) -> None:
    """Registra a mensagem com o traceback completo da exceção atual."""
    _get_logger().exception(message)


def _limpa_valor(value):
    """Decodifica bytes e remove espaços de colunas CHAR."""
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode("cp1252", errors="replace")
    if isinstance(value, str):
        return value.strip()
    return value


def limpar(dataframe: pd.DataFrame) -> pd.DataFrame:
    for column in dataframe.columns:
        if dataframe[column].dtype == object:
            dataframe[column] = dataframe[column].map(_limpa_valor)
    return dataframe


def _cod(value):
    """Normaliza códigos para texto, removendo sufixos decimais inteiros."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (Real, Decimal)) and value == int(value):
        value = int(value)
    normalized = str(value).strip()
    return normalized if normalized else None


def cod(series: pd.Series) -> pd.Series:
    return series.map(_cod).astype(object)


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.map(lambda value: float(value) if isinstance(value, Decimal) else value),
        errors="coerce",
    )


def numerico_se_possivel(series: pd.Series) -> pd.Series:
    """Converte para número apenas quando todos os valores não nulos permitem."""
    converted = pd.to_numeric(series, errors="coerce")
    if converted.notna().sum() != series.notna().sum():
        return series
    valid = converted.dropna()
    if (valid == valid.round()).all():
        return converted.astype("Int64")
    return converted