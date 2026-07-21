import streamlit as st
import pandas as pd
from PIL import Image
# Librerías futuras que usaremos
# import os
# from google import genai
# import gspread

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Sistema Postmortem | Operaciones Digitales",
    page_icon="📋",
    layout="wide"
)

# --- 2. SISTEMA DE AUTENTICACIÓN SIMPLE ---
# En Streamlit Cloud, configuraremos estos correos en st.secrets
# Por ahora, usamos una lista hardcodeada para la prueba inicial.
# IMPORTANTE: Reemplaza con los correos reales de tu equipo.
USUARIOS_AUTORIZADOS = [
    "rojasnunezj@gmail.com",
    "compañero1@pedidosya.com",
    "compañero2@pedidosya.com"
]

def check_login():
    """Maneja el estado de la sesión de login."""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        st.title("🔒 Acceso Restringido")
        st.write("Por favor, ingresa tu correo electrónico autorizado para continuar.")
        
        email_input = st.text_input("Correo electrónico", placeholder="ejemplo@pedidosya.com")
        
        if st.button("Ingresar"):
            if email_input.lower().strip() in [u.lower() for u in USUARIOS_AUTORIZADOS]:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = email_input.lower().strip()
                st.rerun() # Recarga la página para mostrar el contenido
            else:
                st.error("Correo no autorizado. Contacta al administrador.")
        
        return False
    return True

# --- 3. LÓGICA PRINCIPAL DE LA APLICACIÓN ---
def main():
    # Barra lateral
    st.sidebar.title("Menú")
    st.sidebar.write(f"👤 Usuario: {st.session_state['user_email']}")
    if st.sidebar.button("Cerrar Sesión"):
         st.session_state["logged_in"] = False
         st.rerun()

    st.title("Generador Automático de Postmortems")
    st.write("Sube las capturas del caso para extraer la información y generar el documento.")

    # --- ZONA DE SUBIDA DE ARCHIVOS ---
    uploaded_files = st.file_uploader(
        "Sube las capturas de pantalla (Discord, Sistemas, etc.)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        st.success(f"Se han cargado {len(uploaded_files)} imágenes.")
        
        # Mostramos las imágenes en columnas
        cols = st.columns(len(uploaded_files))
        for i, file in enumerate(uploaded_files):
            image = Image.open(file)
            cols[i].image(image, caption=file.name, use_container_width=True)

        st.divider()
        
        # --- BOTÓN DE PROCESAMIENTO (Fase 2) ---
        if st.button("Extraer Datos (Gemini AI)", type="primary"):
            st.info("Iniciando análisis con Gemini... (Esta función se implementará en el siguiente paso)")
            
            # Aquí irá el código para llamar a la API de Gemini
            # y la interfaz para editar los datos extraídos.

if __name__ == "__main__":
    if check_login():
        main()