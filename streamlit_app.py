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
# FUNCIÓN DE DESCARGA
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
df = pd.read_csv("spot.csv", sep=";", encoding="utf-8-sig")
df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
#==========================
# Prepara datos para heatmap
#==========================
df["date"] = df["datetime"].dt.date
df["hour"] = df["datetime"].dt.hour
df_pivot = df.pivot(index="date", columns="hour", values="value")
df_pivot = df_pivot.fillna(0)
df_pivot = df_pivot.sort_index()  # Asegura orden por fecha
df_pivot.index = pd.to_datetime(df_pivot.index)

fechas = pd.to_datetime(df_pivot.index).sort_values().unique()
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
# Gráfico de heatmap con Plotly y superposición de líneas y puntos
#===========================
fig_heat = px.imshow(
    df_pivot.values,
    x=df_pivot.columns,
    y=df_pivot.index.strftime("%Y-%m-%d"),  # convierte fechas a string
    labels=dict(x="Hora", y="Fecha", color="Valor"),
    aspect="auto",
    color_continuous_scale="Turbo"
)
# Convierte el índice datetime a string para que Plotly lo muestre
fig_heat.update_yaxes(tickvals=ticks_mes,
                      tickmode="array",
                      ticktext=[d.strftime("%Y-%m-%d") for d in ticks_mes])

fig_heat.update_xaxes(tickmode="linear", tick0=0, dtick=1)
fig_heat.update_layout(
    height=900,
    xaxis_title="Hora del día",
    yaxis_title="Fecha",
    yaxis=dict(autorange="reversed")  # fechas arriba → abajo
)
#===========================
# Añadir líneas horizontales en los cambios de estación
#===========================
for f in fechas_cambio:
    fig_heat.add_hline(
        y=f,
        line_width=3,
        line_dash="solid",
        line_color="red"
    )
#==========================
# PUNTOS DE SALIDA DEL SOL
#==========================
fig_heat.add_trace(go.Scatter(
    x=df_sun["sunrise_hour"],
    y=df_sun["date"],
    mode="lines",
    line=dict(color="orange", width=3), 
    name="Salida del sol" 
)) 
#==========================
# PUNTOS DE PUESTA DEL SOL
#==========================
fig_heat.add_trace(go.Scatter(
    x=df_sun["sunset_hour"], 
    y=df_sun["date"], 
    mode="lines", 
    line=dict(color="black", width=3), 
    name="Puesta del sol" ))
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

st.title("Visualización de variables ESIOS")

tab_curvas, tab_heatmap = st.tabs(["Curvas", "Heatmap"])

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
    fig_precios = px.line(df_precios, x="datetime", y="valor", color="variable")
    fig_precios.update_layout(
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
    fig_precios.update_xaxes( dtick="D1", tickangle=45)

    # Añadir rectángulos en los fines de semana
    for start, end in weekends:
        fig_precios.add_vrect(
            x0=start, x1=end,
            fillcolor="lightgrey",
            opacity=0.25,
            line_width=0
        )
    st.plotly_chart(fig_precios, width='stretch')


with tab_heatmap:
    st.subheader("Mapa de precios spot histórico")
    st.plotly_chart(fig_heat, width='stretch')

