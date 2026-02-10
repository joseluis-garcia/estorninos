import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ephemData import getSunData
from datetime import date

@st.cache_data
def load_historico_precios_spot(estaciones=True, efemerides=True):
#==========================
# Datos historicos de precios spot para heatmap
#==========================
    df_spot = pd.read_csv(
        "spot.csv",
        sep=";", 
        encoding="utf-8-sig")
    df_spot["datetime"] = pd.to_datetime(df_spot["datetime"], utc=True)
    df_spot["date"] = df_spot["datetime"].dt.date
    df_spot["hour"] = df_spot["datetime"].dt.hour
#==========================
# Prepara datos spot para heatmap
#==========================
    price_matrix = df_spot.pivot(index="date", columns="hour", values="value")
    price_matrix = price_matrix.fillna(0)
    price_matrix = price_matrix.sort_index()  # Asegura orden por fecha
    price_matrix.index = pd.to_datetime(price_matrix.index)

    fechas = pd.to_datetime(price_matrix.index).sort_values().unique()
    ticks_mes = [f for f in fechas if f.day == 1]
#===========================
# Gráfico de heatmap de precios con Plotly
#===========================
    fig_precios = px.imshow(
        price_matrix.values,
        x=price_matrix.columns,
        y=price_matrix.index.strftime("%Y-%m-%d"),  # convierte fechas a string
        labels=dict(x="Hora", y="Fecha", color="Valor"),
        aspect="auto",
        color_continuous_scale="Turbo"
    )
    fig_precios.update_yaxes(tickvals=ticks_mes,
                        tickmode="array",
                        ticktext=[d.strftime("%Y-%m-%d") for d in ticks_mes])

    fig_precios.update_xaxes(tickmode="linear", tick0=0, dtick=1)
    fig_precios.update_layout(
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
                fig_precios.add_hline(
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
        fig_precios.add_trace(go.Scatter(
            x=df_sun["sunrise_hour"],
            y=df_sun["date"],
            mode="lines",
            line=dict(color="orange", width=3), 
            name="Salida del sol", 
        )) 
#==========================
# PUNTOS DE PUESTA DEL SOL
#==========================
        fig_precios.add_trace(go.Scatter(
            x=df_sun["sunset_hour"], 
            y=df_sun["date"], 
            mode="lines", 
            line=dict(color="black", width=3), 
            name="Puesta del sol",
        )) 
    return fig_precios, ticks_mes

