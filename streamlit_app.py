from email.policy import default
import requests
import pandas as pd
from datetime import date, datetime, timedelta
import pytz
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from ephemData import getSunData
import holidays 

# =========================
# CONFIGURACIÓN
# =========================
API_TOKEN = "d24bdfb17a69ea6568815918ee3309c3233ab055fe96340da8cd78e71ee9170e"

BASE_URL = "https://api.esios.ree.es/indicators"

IND_EO = 541   # Previsión eólica
IND_PV = 542   # Previsión solar fotovoltaica
IND_SPOT = 600  # Precio spot
IND_DEM = 603   # Demanda previsión semanal

tz = pytz.timezone("Europe/Madrid")
today = tz.localize(datetime.now().replace(minute=0, second=0, microsecond=0))

headers = {
    "x-api-key": f"{API_TOKEN}",
    "Accept": "application/json;  application/vnd.esios-api-v1+json",
    "Content-Type": "application/json",
    "Host":"api.esios.ree.es",
    "Cookie":""
}

# =========================
# FUNCIÓN DE DESCARGA indicadores ESIOS
# =========================
def get_indicator(indicator_id, date_range):
    url = f"{BASE_URL}/{indicator_id}"
    r = requests.get(url, headers=headers, params=date_range)
    r.raise_for_status()

    json_data = r.json()
    data = json_data["indicator"]["values"]
    variable = json_data["indicator"]["short_name"]

    df = pd.DataFrame(data)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["variable"] = variable
    #df = df.set_index("datetime")
    return df

# =========================
# Rango temporal de analisis hoy menos 5 dias y hoy mas 10 dias en futuro
# =========================
start_date = today + timedelta(days=-5)
end_date = today + timedelta(days=10)

# Para probar fechas fijas
# start_date = tz.localize( datetime(2026, 1, 1).replace(minute=0, second=0, microsecond=0))
# end_date = tz.localize( datetime(2026, 1, 8).replace(minute=0, second=0, microsecond=0))

rango = {
    "start_date": start_date.isoformat(),
    "end_date": end_date.isoformat(),
}
#==========================
# Generar rangos de fines de semana
#==========================
weekends = []
for d in pd.date_range(start_date, end_date):
    if d.weekday() >= 5:  # 5 = sábado, 6 = domingo
        start = pd.Timestamp(d).normalize()
        end = start + pd.Timedelta(days=1)
        weekends.append((start, end))
#==========================
# Generar lista de días festivos en España para el rango de fechas
#==========================
years = list(range(start_date.year, end_date.year + 1))
festivos= holidays.country_holidays("ES", years=years)
festivos = pd.to_datetime(list(festivos.keys())).normalize()
# Rango del eje X (pueden venir como date, datetime o string) 
start_date = pd.to_datetime(start_date).tz_localize(None).normalize() 
end_date = pd.to_datetime(end_date).tz_localize(None).normalize()
festivos = festivos[(festivos >= start_date) & (festivos <= end_date)]
#========================
# Descargar datos de cada indicador
#========================
eolica = get_indicator(IND_EO, rango)[["datetime", "value"]].rename(columns={"value": "eolica"})
solar = get_indicator(IND_PV, rango)[["datetime", "value"]].rename(columns={"value": "solar"})
demanda = get_indicator(IND_DEM, rango)[["datetime", "value"]].rename(columns={"value": "demanda"})
spot = get_indicator(IND_SPOT, rango)
spot = spot[spot['geo_name'] == 'España'] #solo valores de Peninsula
spot = spot[["datetime", "value"]].rename(columns={"value": "precio_spot"})
#=========================
# Combinar datos en un solo DataFrame
#=========================
df_final = eolica.merge(solar, on="datetime", how="outer").merge(demanda, on="datetime", how="outer").merge(spot, on="datetime", how="outer")
df_final["renovable"] = df_final["eolica"] + df_final["solar"]
df_final["precio_estimado"] = (df_final["renovable"] / df_final["demanda"] * (-144.27) + 127.12)
#==========================
# Datos historicos de precios spot para heatmap
#==========================
df_spot = pd.read_csv("spot.csv", sep=";", encoding="utf-8-sig")
df_spot["datetime"] = pd.to_datetime(df_spot["datetime"], utc=True)
df_spot["date"] = df_spot["datetime"].dt.date
df_spot["hour"] = df_spot["datetime"].dt.hour
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
cold_matrix = df_temp.pivot(
    index="date",
    columns="hour",
    values="temperatura",
)
cold_matrix = cold_matrix.fillna(0)
cold_matrix = cold_matrix.sort_index()  # Asegura orden por fecha
cold_matrix.index = pd.to_datetime(cold_matrix.index)
#==========================
# Prepara datos spot para heatmap
#==========================
price_matrix = df_spot.pivot(index="date", columns="hour", values="value")
price_matrix = price_matrix.fillna(0)
price_matrix = price_matrix.sort_index()  # Asegura orden por fecha
price_matrix.index = pd.to_datetime(price_matrix.index)
fechas = pd.to_datetime(price_matrix.index).sort_values().unique()
ticks_mes = [f for f in fechas if f.day == 1]

# Cambios de estación sin año
cambios_estacion = [
    (3, 20),   # primavera
    (6, 21),   # verano
    (9, 22),   # otoño
    (12, 21)   # invierno
]
# Posiciones en el eje Y de los cambios de estación
fechas_cambio = []
for mes, dia in cambios_estacion:
    coincidencias = [f for f in fechas if f.month == mes and f.day == dia]
    fechas_cambio.extend(coincidencias)
#===========================
# Datos de salida y puesta del sol para superponer en el heatmap
#===========================
df_sun = getSunData(date(2024, 1, 1), date(2025, 12, 31), 15)
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
# Convierte el índice datetime a string para que Plotly lo muestre
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
#==========================
# PUNTOS DE SALIDA DEL SOL
#==========================
fig_precios.add_trace(go.Scatter(
    x=df_sun["sunrise_hour"],
    y=df_sun["date"],
    mode="lines",
    line=dict(color="orange", width=3), 
    name="Salida del sol", 
    showlegend=False
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
    showlegend=False
))  

# fig_precios.update_layout(
#     legend=dict(
#         orientation="h",
#         yanchor="bottom",
#         y=1.02,
#         xanchor="left",
#         x=0
#     )
# )


#==========================
# Dias fríos superpuestos como un heatmap semitransparente
#==========================
# fig_precios.add_trace(
#     go.Heatmap(
#         z=cold_matrix.values,
#         x=cold_matrix.columns,
#         y=cold_matrix.index,
#         colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,255,1)"]],
#         showscale=True,
#         hoverinfo="skip"
#     )
# )
# fig_precios.add_trace(
#     go.Heatmap( 
#         z=cold_z,
#         x=cold_x,
#         y=cold_y, 
#         colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,255,0,0.30)"]],
#         showscale=False, 
#         hoverinfo="skip" 
#         )
# )
# print("Añadiendo días fríos al heatmap")
# fig_precios.add_trace(
#     go.Contour(
#         z=cold_z,
#         x=cold_x,
#         y=cold_y,
#         contours=dict(
#             start=0.5,
#             end=0.5,
#             size=1,
#             coloring="none"   # solo líneas, sin relleno
#         ),
#         line=dict(
#             width=2,
#             color="rgba(255, 255, 255, 0.9)"  # color del contorno
#         ),
#         showscale=False,
#         hoverinfo="skip"
#     )
# )


# =========================
# DEFINICION UI
# =========================
st.markdown("""
<style>

/* Contenedor general de las tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 14px !important;                 /* separación entre pestañas */
    padding-top: 6px !important;
    padding-bottom: 6px !important;
}

/* Cada pestaña (texto y padding) */
.stTabs [data-baseweb="tab"] {
    font-size: 22px !important;           /* tamaño del texto */
    font-weight: 600 !important;          /* grosor */
    padding: 12px 22px !important;        /* tamaño de la pestaña */
    border-radius: 6px !important;
}

/* Pestaña seleccionada */
.stTabs [aria-selected="true"] {
    background-color: #1f77b4 !important; /* color de fondo */
    color: white !important;              /* color del texto */
}

/* Pestañas no seleccionadas */
.stTabs [aria-selected="false"] {
    background-color: #e6e6e6 !important;
    color: #333 !important;
}

</style>
""", unsafe_allow_html=True)
st.set_page_config(layout="wide")

st.title("Visualización de variables ESIOS")

tab_curvas, tab_precios, tab_temperaturas, tab_summary = st.tabs(["Curvas", "Precios", "Temperaturas", "Resumen"])

with tab_curvas:
    # Rango de fechas
    min_date = df_final["datetime"].min()
    max_date = df_final["datetime"].max()
    st.info(f"Rango de fechas: {min_date} → {max_date}")

    st.subheader("Predicción Energia")

    columnas = st.multiselect(
        "Selecciona columnas",
        options=[c for c in df_final.columns if c != "datetime"],
        default=['eolica', 'solar', 'demanda', 'renovable']
    )

    if columnas:
        df_energia = df_final.melt(id_vars="datetime", value_vars=columnas,
                        var_name="variable", value_name="valor")
        fig_energia = px.line(df_energia, x="datetime", y="valor", color="variable")
        fig_energia.update_layout(
            legend=dict(
                orientation="h",          # horizontal
                yanchor="top",
                y=-0.2,                   # desplaza la leyenda hacia abajo
                xanchor="center",
                x=0.5
            ),
            xaxis_title="Fecha y hora",
            yaxis_title="MWh",
            hovermode="x unified"
        )
        fig_energia.update_xaxes( dtick="D1", tickangle=45)

        # Añadir rectángulos en los fines de semana
        for start, end in weekends:
            fig_energia.add_vrect(
                x0=start, x1=end,
                fillcolor="lightgrey",
                opacity=0.25,
                line_width=0
            )
        # Añadir rectángulos en los días festivos
        for festivo in festivos:
            fig_energia.add_vrect(
                x0=festivo, x1=festivo + pd.Timedelta(days=1),
                fillcolor="indianred",
                opacity=0.25,
                line_width=0
            )
        st.plotly_chart(fig_energia, width='stretch')

# =========================
# Prepara gráfico de precios
# =========================
    st.subheader("Predicción Precios")
    df_precios = df_final.melt(id_vars="datetime", value_vars=["precio_estimado", "precio_spot"],
                        var_name="variable", value_name="valor")
    fig_estimacion = px.line(df_precios, x="datetime", y="valor", color="variable")
    fig_estimacion.update_layout(
        legend=dict(
            orientation="h",          # horizontal
            yanchor="top",
            y=-0.2,                   # desplaza la leyenda hacia abajo
            xanchor="center",
            x=0.5
        ),
        margin=dict(t=20, b=20, l=0, r=0),
        xaxis_title="Fecha y hora",
        yaxis_title="€/MWh",
        hovermode="x unified"
    )
    fig_estimacion.update_xaxes( dtick="D1", tickangle=45)

    # Añadir rectángulos en los fines de semana
    for start, end in weekends:
        fig_estimacion.add_vrect(
            x0=start, x1=end,
            fillcolor="lightgrey",
            opacity=0.25,
            line_width=0
        )
    st.plotly_chart(fig_estimacion, width='stretch', key="estimacion")


with tab_precios:
    st.subheader("Mapa de precios spot histórico")
    st.plotly_chart(fig_precios, width='stretch', key="precios")

with tab_temperaturas:
    st.subheader("Mapa de temperaturas históricas")
    st.plotly_chart(fig_temperaturas, width='stretch', key="temperaturas")

with tab_summary:
    common_layout = dict( height=400, margin=dict(l=0, r=0, t=40, b=40) )
    fig_precios.update_layout(**common_layout) 
    fig_temperaturas.update_layout(**common_layout) 
    # fig_precios.update_coloraxes(showscale=False) 
    # fig_temperaturas.update_coloraxes(showscale=False)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Precios")
        st.plotly_chart(fig_precios, width='stretch', key="hm1")

    with col2:
        st.subheader("Temperaturas")
        st.plotly_chart(fig_temperaturas, width='stretch', key="hm2")



