from email.policy import default
import requests
import pandas as pd
from datetime import date, datetime, timedelta
import pytz
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from historico_temperaturas import load_historico_temperaturas
from historico_spot import load_historico_precios_spot
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


def px_to_trace(px_fig, colorbar_side="right", colorscale=None, colorbar_len=0.9, colorbar_x=None):
    """
    Convierte un px.imshow() en un trace de go.Heatmap listo para subplots.
    
    Args:
        px_fig: figura de plotly.express creada con px.imshow()
        colorbar_side: "left" o "right" (posición de la colorbar)
        colorscale: opcional, cambiar la escala de colores
        colorbar_len: longitud relativa de la colorbar (0-1)
        colorbar_x: posición exacta en el papel (si quieres controlar manualmente)
        
    Returns:
        go.Heatmap trace listo para add_trace()
    """
    trace = px_fig.data[0]  # solo hay un trace en px.imshow
    
    # Desvincular de coloraxis
    trace.update(coloraxis=None, showscale=True)
    
    # Ajustar colores
    if colorscale is not None:
        trace.update(colorscale=colorscale)
    
    # Posición de la colorbar
    if colorbar_x is None:
        colorbar_x = -0.08 if colorbar_side == "left" else 1.08
    
    trace.update(
        colorbar=dict(
            x=colorbar_x,
            xanchor="right" if colorbar_side == "left" else "left",
            len=colorbar_len,
            ticklabelposition="outside" if colorbar_side=="right" else "outside left"
        )
    )
    
    return trace


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
        fig_energia.add_vline(x=today, line_width=4, line_dash="dash", line_color="green", name="Hoy")

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
    fig_estimacion.add_vline(x=today, line_width=4, line_dash="dash", line_color="green", name="Hoy")
    st.plotly_chart(fig_estimacion, width='stretch', key="estimacion")


with tab_precios:
    fig_precios, ticks_mes = load_historico_precios_spot(True, True)
    st.subheader("Mapa de precios spot histórico")
    st.plotly_chart(fig_precios, width='stretch', key="precios")

with tab_temperaturas:
    fig_temperaturas, ticks_mes = load_historico_temperaturas(True, True)
    st.subheader("Mapa de temperaturas históricas")
    st.plotly_chart(fig_temperaturas, width='stretch', key="temperaturas")

with tab_summary:

    # Crear subplots con eje Y compartido
    fig_comb = make_subplots(
        rows=1, 
        cols=3,
        column_widths=[0.45, 0.1, 0.45],  # ejeY ocupa poco
        shared_yaxes=True,
        horizontal_spacing=0.05
    )

    # Convertir px.imshow() a traces limpios
    trace1 = px_to_trace(fig_precios, colorbar_side="left", colorscale="Turbo")
    trace2 = px_to_trace(fig_temperaturas, colorbar_side="right", colorscale="RdBu_r")

    # Añadir al subplot
    fig_comb.add_trace(trace1, row=1, col=1)
    fig_comb.add_trace(trace2, row=1, col=3)

# --- Eje Y central (solo etiquetas) ---
    fig_comb.add_trace(
        go.Scatter(
            x=[0]*len(ticks_mes),
            y=ticks_mes,
            text=[d.strftime("%Y-%m") for d in ticks_mes],
            mode="text",
            showlegend=False
        ),
        row=1,
        col=2
    )

    # Hacer que el eje Y exista
    fig_comb.update_yaxes(visible=True, showticklabels=False, row=1, col=2)



    # Ocultar los ejes del subplot central
    fig_comb.update_xaxes(visible=False, row=1, col=2)
    fig_comb.update_yaxes(visible=False, row=1, col=2)

    # Ocultar eje Y del segundo heatmap
    fig_comb.update_yaxes(showticklabels=False, row=1, col=1)
    fig_comb.update_yaxes(showticklabels=False, row=1, col=3)

    # Ajustar layout
    fig_comb.update_layout(
        height=900,
        margin=dict(l=30, r=30, t=40, b=40)
    )

    # Mostrar en Streamlit
    st.subheader("Mapa de temperaturas y precios históricos")
    st.plotly_chart(fig_comb, width='stretch', key="resumen")

