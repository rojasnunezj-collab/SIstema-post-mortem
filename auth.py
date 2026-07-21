# auth.py
import streamlit as st
from config import USUARIOS_AUTORIZADOS

def check_login():
    """Maneja el estado de la sesión de login."""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        st.title("🔒 Acceso Restringido")
        st.write("Por favor, ingresa tu correo electrónico autorizado para continuar.")
        
        email_input = st.text_input("Correo electrónico", placeholder="ejemplo@pedidosya.com")
        
        if st.button("Ingresar"):
            # Compara el correo ingresado (limpio de espacios y en minúsculas) con los autorizados
            if email_input.lower().strip() in [u.lower() for u in USUARIOS_AUTORIZADOS]:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = email_input.lower().strip()
                st.rerun() # Recarga la página para mostrar la app
            else:
                st.error("Correo no autorizado. Contacta al administrador.")
        
        return False
    return True