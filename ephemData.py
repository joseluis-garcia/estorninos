import streamlit as st
import ephem
import pandas as pd
from datetime import date, timedelta

# =========================
# FUNCION PARA OBTENER HORAS DE SALIDA Y PUESTA DEL SOL
# start: fecha de inicio
# end: fecha de fin
# delta: intervalo en días
# return: dataframe con columnas "date", "sunrise_hour" y "sunset_hour"
# =========================
@st.cache_data
def getSunData( start, end, delta):
    # Coordenadas de Madrid
    lat = '40.4165'
    lon = '-3.70256'

    # Configurar observador
    madrid = ephem.Observer()
    madrid.lat = lat
    madrid.lon = lon

    rows = []
    d = start

    while d <= end:
        madrid.date = d

        sunrise = madrid.next_rising(ephem.Sun()).datetime()
        sunset  = madrid.next_setting(ephem.Sun()).datetime()

        rows.append({
            "date": d,
            "sunrise_hour": sunrise.hour + sunrise.minute/60,
            "sunset_hour": sunset.hour + sunset.minute/60
        })

        d += timedelta(days=delta)

    return pd.DataFrame(rows)
