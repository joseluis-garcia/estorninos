import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ephemData import getSunData
from datetime import date

@st.cache_data
def load_historico_temperaturas(estaciones=True, efemerides=True):
#==========================
# Datos historicos de temperaturas para heatmap
#==========================
    df_temp = pd.read_csv(
        "temperaturas.csv",
        sep=";", 
        encoding="utf-8-sig",
        parse_dates=["datetime"],
        dayfirst=True,               # importante para formato europeo
        date_format="%d/%m/%Y %H:%M"
    )
    df_temp["datetime"] = pd.to_datetime(df_temp["datetime"])
    df_temp["date"] = df_temp["datetime"].dt.date
    df_temp["hour"] = df_temp["datetime"].dt.hour
#==========================
# Prepara datos temperatura para heatmap
#==========================
    cold_matrix = df_temp.pivot(
        index="date",
        columns="hour",
        values="temperatura",
    )
    cold_matrix = cold_matrix.fillna(0)
    cold_matrix = cold_matrix.sort_index()  # Asegura orden por fecha
    cold_matrix.index = pd.to_datetime(cold_matrix.index)
    fechas = pd.to_datetime(cold_matrix.index).sort_values().unique()
    ticks_mes = [f for f in fechas if f.day == 1]
#===========================
# Gráfico de heatmap de precios con Plotly
#===========================
    fig_temperaturas = px.imshow(
        cold_matrix.values,
        x=cold_matrix.columns,
        y=cold_matrix.index.strftime("%Y-%m-%d"),  # convierte fechas a string
        labels=dict(x="Hora", y="Fecha", color="Valor"),
        aspect="auto",
        color_continuous_scale="RdBu_r"
    )
    fig_temperaturas.update_yaxes(tickvals=ticks_mes,
                        tickmode="array",
                        ticktext=[d.strftime("%Y-%m-%d") for d in ticks_mes])
    fig_temperaturas.update_xaxes(tickmode="linear", tick0=0, dtick=1)
    fig_temperaturas.update_layout(
        height=900,
        xaxis_title="Hora del día",
        yaxis_title="Fecha",
        yaxis=dict(autorange="reversed")  # fechas arriba → abajo
    )

    if (estaciones):
    #===========================
    # Cambios de estación sin año
    #===========================
        cambios_estacion = [
            (3, 20),   # primavera
            (6, 21),   # verano
            (9, 22),   # otoño
            (12, 21)   # invierno
        ]
    #===========================
    # Posiciones en el eje Y de los cambios de estación
    #===========================
        fechas_cambio = []
        for mes, dia in cambios_estacion:
            coincidencias = [f for f in fechas if f.month == mes and f.day == dia]
            fechas_cambio.extend(coincidencias)
    #===========================
    # Añadir líneas horizontales en los cambios de estación
    #===========================
            for f in fechas_cambio:
                fig_temperaturas.add_hline(
                    y=f,
                    line_width=3,
                    line_dash="solid",
                    line_color="red"
                )
    if (efemerides):
#===========================
# Datos de salida y puesta del sol para superponer en el heatmap
#===========================
        df_sun = getSunData(date(2024, 1, 1), date(2025, 12, 31), 15)
#==========================
# PUNTOS DE SALIDA DEL SOL
#==========================
        fig_temperaturas.add_trace(go.Scatter(
            x=df_sun["sunrise_hour"],
            y=df_sun["date"],
            mode="lines",
            line=dict(color="orange", width=3), 
            name="Salida del sol"
        )) 
#==========================
# PUNTOS DE PUESTA DEL SOL
#==========================
        fig_temperaturas.add_trace(go.Scatter(
            x=df_sun["sunset_hour"], 
            y=df_sun["date"], 
            mode="lines", 
            line=dict(color="black", width=3), 
            name="Puesta del sol"
        )) 
    return fig_temperaturas, ticks_mes

# Define la temperatura umbral para considerar un día como frío y generar matriz de días fríos para superponer en el heatmap
#==========================
# umbral = st.number_input("Umbral de temperatura", value=5.0)
# df_temp["is_cold"] = df_temp["temperatura"] < umbral
# cold_matrix = df_temp.pivot_table(
#     index="date",
#     columns="hour",
#     values="is_cold",
#     aggfunc="max"   # si hay varios registros por hora, basta con que uno sea frío
# )
# cold_x = cold_matrix.columns.astype(int)
# cold_y = pd.to_datetime(cold_matrix.index).sort_values().unique()
# cold_z = cold_matrix.fillna(0).astype(int).values

#cold_z = cold_matrix.astype(int).values
# cold_x = pd.to_datetime(cold_matrix.columns)
# cold_y = cold_matrix.index.astype(int)
# cold_matrix = df_temp.pivot(
#     index="date",
#     columns="hour",
#     values="temperatura",
# )
# cold_matrix = cold_matrix.fillna(0)
# cold_matrix = cold_matrix.sort_index()  # Asegura orden por fecha
# cold_matrix.index = pd.to_datetime(cold_matrix.index)