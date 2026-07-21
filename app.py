# app.py
import streamlit as st
from PIL import Image

from config import LIMITES_PAIS
from auth import check_login
from gemini_api import extraer_datos_gemini

st.set_page_config(page_title="Sistema Postmortem | Operaciones Digitales", page_icon="📋", layout="wide")

def main():
    st.sidebar.title("Menú")
    st.sidebar.write(f"👤 Usuario: {st.session_state.get('user_email', '')}")
    if st.sidebar.button("Cerrar Sesión"):
         st.session_state["logged_in"] = False
         st.rerun()

    st.title("Generador Automático de Postmortems")
    st.write("Sube las capturas del caso para extraer la información.")

    uploaded_files = st.file_uploader("Sube las capturas de pantalla", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

    if uploaded_files:
        cols = st.columns(len(uploaded_files))
        for i, file in enumerate(uploaded_files):
            image = Image.open(file)
            cols[i].image(image, caption=file.name, use_container_width=True)

        st.divider()
        
        if st.button("Extraer Datos (Gemini AI)", type="primary"):
            with st.spinner("Analizando la imagen..."):
                imagen_principal = Image.open(uploaded_files[0])
                datos = extraer_datos_gemini(imagen_principal)
                
                if datos:
                    st.session_state["datos_extraidos"] = datos
                    st.success("✅ ¡Datos extraídos con éxito!")
        
        if "datos_extraidos" in st.session_state:
            st.subheader("Auditoría de Datos y Cálculos")
            d = st.session_state["datos_extraidos"]
            
            with st.form("form_postmortem"):
                col1, col2 = st.columns(2)
                
                with col1:
                    caso_nro = st.text_input("Número de Caso", value=d.get("numero_caso", ""))
                    hora = st.text_input("Hora", value=d.get("hora", ""))
                    agente = st.text_input("Agente", value=d.get("agente_escala", ""))
                    pais = st.text_input("País", value=d.get("pais", ""))
                    
                    limite_pais = LIMITES_PAIS.get(d.get("pais", ""), 0)
                    st.caption(f"Límite máximo para {d.get('pais', 'País')}: **${limite_pais}**")
                
                with col2:
                    correo = st.text_input("Correo", value=d.get("correo", ""))
                    order_id = st.text_input("Order ID", value=d.get("order_id", ""))
                    ccr3 = st.text_input("CCR3 Sugerido (Próximamente desde Sheet)", value=d.get("ccr3", ""))
                    fin_accion = st.text_input("Fin de Acción (Ingreso manual)", placeholder="Ej: 6:15 PM")
                
                problema = st.text_area("Problema Reportado (Resumido)", value=d.get("motivo_reclamo", ""), height=80)
                
                st.divider()
                st.markdown("### Cálculos Financieros")
                
                # ATRAPAMOS LOS MONTOS QUE ENVÍA LA IA (Asegurándonos de que sean números)
                monto_p_ia = float(d.get("monto_pedido", 0.0) if d.get("monto_pedido") else 0.0)
                monto_d_ia = float(d.get("monto_devolucion", 0.0) if d.get("monto_devolucion") else 0.0)

                col3, col4 = st.columns(2)
                
                with col3:
                    monto_pedido = st.number_input("Monto del Pedido ($)", min_value=0.0, value=monto_p_ia, step=10.0)
                    devolucion = st.number_input("Monto de Devolución ($)", min_value=0.0, value=monto_d_ia, step=10.0)
                
                with col4:
                    compensacion = devolucion # SOP indica que es el 100%
                    total = devolucion + compensacion
                    
                    st.metric("Compensación Automática (100%)", f"${compensacion:.2f}")
                    st.metric("Total (Protocolo VIP)", f"${total:.2f}")
                    
                    if total > limite_pais and limite_pais > 0:
                        st.error("⚠️ ALERTA: El total SUPERA el límite del país.")
                    elif limite_pais > 0 and total > 0:
                        st.success("✅ El total está dentro del límite permitido.")

                st.divider()
                st.markdown("### Corrección de Estilo (Borrador de Resolución)")
                resolucion = st.text_area("Pega aquí tu borrador. La IA lo limpiará de muletillas en el siguiente paso.", height=150)
                
                submit = st.form_submit_button("Aprobar Datos y Continuar", type="primary")

if __name__ == "__main__":
    if check_login():
        main()