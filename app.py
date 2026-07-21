# app.py
import streamlit as st
from PIL import Image

# Importamos nuestros propios módulos
from config import LIMITES_PAIS
from auth import check_login
from gemini_api import extraer_datos_gemini

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Sistema Postmortem | Operaciones Digitales",
    page_icon="📋",
    layout="wide"
)

def main():
    # --- BARRA LATERAL ---
    st.sidebar.title("Menú")
    st.sidebar.write(f"👤 Usuario: {st.session_state.get('user_email', '')}")
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
        cols = st.columns(len(uploaded_files))
        for i, file in enumerate(uploaded_files):
            image = Image.open(file)
            cols[i].image(image, caption=file.name, use_container_width=True)

        st.divider()
        
        # --- BOTÓN DE PROCESAMIENTO ---
        if st.button("Extraer Datos (Gemini AI)", type="primary"):
            with st.spinner("Analizando imágenes con Inteligencia Artificial..."):
                imagen_principal = Image.open(uploaded_files[0])
                datos = extraer_datos_gemini(imagen_principal)
                
                if datos:
                    st.session_state["datos_extraidos"] = datos
                    st.success("✅ ¡Datos extraídos con éxito!")
        
        # --- FORMULARIO DE AUDITORÍA Y CÁLCULOS ---
        if "datos_extraidos" in st.session_state:
            st.subheader("Auditoría de Datos y Cálculos")
            st.info("Revisa la información extraída. Puedes editar cualquier campo manualmente si es necesario.")
            
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
                    ccr3 = st.text_input("CCR3 Sugerido (Puedes editarlo)", value=d.get("ccr3", ""))
                    fin_accion = st.text_input("Fin de Acción (Ingreso manual)", placeholder="Ej: 6:15 PM")
                
                problema = st.text_area("Problema Reportado", value=d.get("motivo_reclamo", ""), height=80)
                
                st.divider()
                st.markdown("### Cálculos Financieros")
                col3, col4 = st.columns(2)
                
                with col3:
                    monto_pedido = st.number_input("Monto del Pedido ($)", min_value=0.0, value=0.0, step=100.0)
                    devolucion = st.number_input("Monto de Devolución ($)", min_value=0.0, value=0.0, step=100.0)
                
                with col4:
                    compensacion = devolucion # El SOP indica que es el 100%
                    total = devolucion + compensacion
                    
                    st.metric("Compensación Automática (100%)", f"${compensacion:.2f}")
                    st.metric("Total (Protocolo VIP)", f"${total:.2f}")
                    
                    if total > limite_pais and limite_pais > 0:
                        st.error("⚠️ ALERTA: El total SUPERA el límite del país.")
                    elif limite_pais > 0 and total > 0:
                        st.success("✅ El total está dentro del límite permitido.")

                st.divider()
                st.markdown("### Corrección de Estilo (Borrador de Resolución)")
                resolucion = st.text_area(
                    "Pega aquí tu borrador. La IA lo limpiará de muletillas y mejorará el estilo corporativo en el siguiente paso.", 
                    height=150
                )
                
                submit = st.form_submit_button("Aprobar Datos y Continuar (Próximamente)", type="primary")
                
                if submit:
                    st.warning("Estructura lista. En la Fase 3 integraremos la reescritura del texto y la generación del Google Doc.")

# --- PUNTO DE ENTRADA ---
if __name__ == "__main__":
    if check_login():
        main()