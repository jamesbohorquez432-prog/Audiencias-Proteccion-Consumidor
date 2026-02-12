# app.py
import re
from datetime import datetime, time
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------
# Configuración
# ---------------------------
st.set_page_config(page_title="Audiencias DAJ", layout="wide")

# ---------------------------
# Rutas de archivos
# ---------------------------
BASE_DIR = Path(__file__).parent
ARCHIVO_EXCEL = BASE_DIR / "audiencias.xlsx"

IMAGES_DIR = BASE_DIR / "images"
LOGO_SIC = IMAGES_DIR / "logo_sic.png"
LOGO_COL = IMAGES_DIR / "logo_colombia.png"

# ---------------------------
# Columnas del Excel (AJUSTA SI CAMBIAN)
# ---------------------------
COLUMNA_FECHA_HORA = "Fecha y hora Audiencia"
COLUMNA_RADICADO = "Radicado"
COLUMNA_DEMANDANTE = "Demandante"
COLUMNA_DEMANDADO = "Demandado"
COLUMNA_SALA = "Sala Audiencia"
COLUMNA_JUEZ = "Juez"  # (antes Aprobador)

# ---------------------------
# Encabezado con imágenes
# ---------------------------
c1, c2, c3 = st.columns([1, 4, 1])

with c1:
    if LOGO_COL.exists():
        st.image(str(LOGO_COL), use_container_width=True)

with c2:
    st.markdown("## Publicación informativa de audiencias - Protección al Consumidor")
    st.caption("Consulta interna informativa. No reemplaza la notificación procesal.")
#####ojo james en esta linea va lo de la imagen 
# ---------------------------
# Función: texto español → datetime
# ---------------------------
def parse_fecha_es(valor):
    if pd.isna(valor):
        return pd.NaT

    # Si ya viene como datetime desde Excel, perfecto
    if isinstance(valor, (datetime, pd.Timestamp)):
        return pd.to_datetime(valor, errors="coerce")

    texto = str(valor).strip().lower()
    texto = re.sub(r"\s+", " ", texto)

    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "setiembre": "09",
        "octubre": "10", "noviembre": "11", "diciembre": "12",
    }

    # "21 de enero de 2026 2:00 PM" -> "21/01/2026 2:00 PM"
    for mes, num in meses.items():
        texto = texto.replace(f" de {mes} de ", f"/{num}/")

    texto = texto.replace(" am", " AM").replace(" pm", " PM")

    # Intento 1: formato exacto
    try:
        return datetime.strptime(texto, "%d/%m/%Y %I:%M %p")
    except:
        # Intento 2: pandas flexible
        return pd.to_datetime(texto, errors="coerce")


# ---------------------------
# Exportar a Excel
# ---------------------------
def df_to_excel_bytes(df_export):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Resultados")
    return output.getvalue()


# ---------------------------
# Cargar Excel
# ---------------------------
try:
    df = pd.read_excel(ARCHIVO_EXCEL, engine="openpyxl")
except Exception as e:
    st.error(f"No se pudo abrir el archivo Excel: {ARCHIVO_EXCEL}\n\nDetalle: {e}")
    st.stop()

df.columns = [c.strip() for c in df.columns]

# Validar columnas requeridas
requeridas = [
    COLUMNA_FECHA_HORA, COLUMNA_RADICADO,
    COLUMNA_DEMANDANTE, COLUMNA_DEMANDADO,
    COLUMNA_SALA, COLUMNA_JUEZ
]
faltan = [c for c in requeridas if c not in df.columns]
if faltan:
    st.error(f"Faltan columnas en el Excel: {faltan}")
    st.stop()

# ---------------------------
# Preparar fechas
# ---------------------------
df["fecha_hora"] = df[COLUMNA_FECHA_HORA].apply(parse_fecha_es)
df = df.dropna(subset=["fecha_hora"]).copy()

df["fecha"] = pd.to_datetime(df["fecha_hora"]).dt.date
df["hora"] = pd.to_datetime(df["fecha_hora"]).dt.time

# Sala numérica para ordenar bien
df["_sala_num"] = pd.to_numeric(df[COLUMNA_SALA], errors="coerce")

min_f = df["fecha"].min()
max_f = df["fecha"].max()

# ---------------------------
# Filtros
# ---------------------------
st.subheader("Filtros")

c1, c2, c3, c4 = st.columns(4)

with c1:
    rango_fechas = st.date_input("Rango de fechas", (min_f, max_f))

with c2:
    hora_desde = st.time_input("Hora desde", time(0, 0))

with c3:
    hora_hasta = st.time_input("Hora hasta", time(23, 59))

# Sala (ordenada)
salas = sorted(df["_sala_num"].dropna().astype(int).unique())
salas_opciones = ["Todas"] + [str(s) for s in salas]

with c4:
    sala_sel = st.selectbox("Sala de audiencia", salas_opciones)

radicado_txt = st.text_input("Radicado contiene")
partes_txt = st.text_input("Demandante o Demandado contiene")

# Juez (desplegable)
jueces = sorted(
    df[COLUMNA_JUEZ]
    .dropna()
    .astype(str)
    .str.strip()
    .unique()
)
juez_opciones = ["Todos"] + jueces
juez_sel = st.selectbox("Juez / Abogado", juez_opciones)

# ---------------------------
# Aplicar filtros
# ---------------------------
f = df.copy()

# rango fechas
desde, hasta = rango_fechas
f = f[(f["fecha"] >= desde) & (f["fecha"] <= hasta)]

# rango horas
f = f[(f["hora"] >= hora_desde) & (f["hora"] <= hora_hasta)]

# sala
if sala_sel != "Todas":
    f = f[f["_sala_num"] == int(sala_sel)]

# juez
if juez_sel != "Todos":
    f = f[f[COLUMNA_JUEZ].astype(str).str.strip() == juez_sel]

# radicado
if radicado_txt:
    f = f[f[COLUMNA_RADICADO].astype(str).str.contains(radicado_txt, case=False, na=False)]

# partes
if partes_txt:
    f = f[
        f[COLUMNA_DEMANDANTE].astype(str).str.contains(partes_txt, case=False, na=False) |
        f[COLUMNA_DEMANDADO].astype(str).str.contains(partes_txt, case=False, na=False)
    ]

# orden final: sala, fecha/hora
f = f.sort_values(["_sala_num", "fecha_hora"])

# ---------------------------
# Indicadores
# ---------------------------
st.subheader("Indicadores")
st.metric("Audiencias encontradas", len(f))

# ---------------------------
# Resultados
# ---------------------------
st.subheader("Resultados")

columnas_mostrar = [
    COLUMNA_RADICADO,
    COLUMNA_DEMANDANTE,
    COLUMNA_DEMANDADO,
    COLUMNA_FECHA_HORA,
    COLUMNA_SALA,
    COLUMNA_JUEZ,
]

vista = f[columnas_mostrar].copy()
st.dataframe(vista, use_container_width=True, hide_index=True)

# ---------------------------
# Exportar
# ---------------------------
st.subheader("Exportar a Excel")

if len(vista) > 0:
    excel_bytes = df_to_excel_bytes(vista)
    st.download_button(
        "Descargar resultados (Excel)",
        data=excel_bytes,
        file_name="audiencias_filtradas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("No hay resultados para exportar.")