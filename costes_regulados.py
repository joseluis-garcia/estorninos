"""
tarifa_20TD.py

Cálculo de periodos P1–P3 y costes regulados (peajes, cargos y pagos por capacidad)
para la tarifa 2.0TD en España.

NOTA:
Los valores de peajes, cargos y pagos por capacidad son EJEMPLOS.
Debes sustituirlos por los valores vigentes del BOE.
"""

import datetime as dt
from typing import Union
import pandas as pd
import holidays
import json




# # ==========================
# # 1. PARÁMETROS REGULADOS
# # ==========================

# # Peajes de energía 2.0TD (€/kWh) - EJEMPLOS
# peajes_energia = {
#     "P1": 0.033261,
#     "P2": 0.016409,
#     "P3": 0.000077,
# }

# # Cargos de energía 2.0TD (€/kWh) - EJEMPLOS
# cargos_energia = {
#     "P1": 0.012858,
#     "P2": 0.064292,
#     "P3": 0.003215,
# }

# # Pagos por capacidad 2.0TD (€/kWh) - EJEMPLOS
# pagos_capacidad = {
#     "P1": 0.00050,
#     "P2": 0.00050,
#     "P3": 0.00050,
# }


# ==========================
# 2. FESTIVOS CON `holidays`
# ==========================

festivos = holidays.country_holidays("ES",years=range(2026, 2027), subdiv="MD")
festivos = pd.to_datetime(list(festivos.keys())).normalize()

def es_festivo_o_fin_de_semana(fecha: dt.datetime) -> bool:
    if fecha in festivos:
        return True
    if fecha.weekday() >= 5:  # sábado/domingo
        return True
    return False

# ==========================
# 3. PERIODO 2.0TD P1–P3
# ==========================

def periodo_2_0TD(fecha: dt.datetime | pd.Timestamp) -> str:
    """
    Determina el periodo tarifario P1–P3 para energía en 2.0TD.
    """

    fecha = pd.to_datetime(fecha)
    h = fecha.hour

    # Festivos y fines de semana → todo P3 (valle)
    if es_festivo_o_fin_de_semana(fecha):
        return "P3"

    # Horario valle (P3)
    if 0 <= h < 8:
        return "P3"

    # Horario punta (P1)
    if 10 <= h < 14 or 18 <= h < 22:
        return "P1"

    # Horario llano (P2)
    return "P2"


# ==========================
# 4. COSTES REGULADOS
# ==========================

def costes_regulados(df: pd.DataFrame, col_datetime: str) -> pd.DataFrame:
    """
    Añade columnas:
    - periodo (P1–P3)
    - peaje
    - cargo
    - capacidad
    - coste_regulado
    """

    with open("costes_regulados.json", "r", encoding="utf-8") as f:
        costes = json.load(f)["cargos"]

    df = df.copy()
    df[col_datetime] = pd.to_datetime(df[col_datetime])
    print(costes)
    df["periodo"] = df[col_datetime].apply(periodo_2_0TD)
    
    df["peaje"] = df.apply(
    lambda row: costes[str(row[col_datetime].year)]["peaje"][row["periodo"]],
    axis=1
)
    df["cargo"] = df.apply(
    lambda row: costes[str(row[col_datetime].year)]["cargo"][row["periodo"]],
    axis=1
)
    df["capacidad"] = df.apply(
    lambda row: costes[str(row[col_datetime].year)]["capacidad"][row["periodo"]],
    axis=1
)
    df["coste_regulado"] = df["peaje"] + df["cargo"] + df["capacidad"]

    return df
