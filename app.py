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
                    caso = st.text_input("Caso", value=d.get("caso", ""))
                    hora = st.text_input("Hora", value=d.get("hora", ""))
                    inicio_pm = st.text_input("Inicio PM (Ingreso manual)", placeholder="Ej: 6:00 PM")
                    agente = st.text_input("Agente", value=d.get("agente_escala", ""))
                    pais = st.text_input("País", value=d.get("pais", ""))
                    numeros = st.text_input("Números", value=d.get("numeros", ""))
                    fraude_operacional = st.text_input("Fraude Operacional", value=d.get("fraude_operacional", ""))
                    contactos = st.text_input("Contactos", value=d.get("contactos", ""))
                    
                    limite_pais = LIMITES_PAIS.get(d.get("pais", ""), 0)
                    st.caption(f"Límite máximo para {d.get('pais', 'País')}: **${limite_pais}**")
                
                with col2:
                    correo = st.text_input("Correo", value=d.get("correo", ""))
                    order_id = st.text_input("Order ID", value=d.get("order_id", ""))
                    user_id = st.text_input("User ID", value=d.get("user_id", ""))
                    pedido_link = st.text_input("Link Pedido", value=d.get("pedido_link", ""))
                    ccr3 = st.text_input("CCR3", value=d.get("ccr3", ""))
                    fin_accion = st.text_input("Fin de Acción (Ingreso manual)", placeholder="Ej: 6:15 PM")
                    fraude_fintech = st.text_input("Fraude Fintech", value=d.get("fraude_fintech", ""))
                    seguidores = st.text_input("Seguidores", value=d.get("seguidores", ""))
                
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

            if submit:
                # 1. Reunir los datos finales (con posibles ediciones manuales)
                datos_finales = {
                    "numero_caso": caso_nro,
                    "caso": caso,
                    "hora": hora,
                    "inicio_pm": inicio_pm,
                    "fin_accion": fin_accion,
                    "agente_escala": agente,
                    "pais": pais,
                    "correo": correo,
                    "order_id": order_id,
                    "user_id": user_id,
                    "pedido_link": pedido_link,
                    "ccr3": ccr3,
                    "motivo_reclamo": problema,
                    "monto_pedido": monto_pedido,
                    "monto_devolucion": devolucion,
                    "compensacion": compensacion,
                    "total": total,
                    "numeros": numeros,
                    "fraude_operacional": fraude_operacional,
                    "fraude_fintech": fraude_fintech,
                    "seguidores": seguidores,
                    "contactos": contactos,
                    "limite": limite_pais,
                    "evaluacion_limite": "no PASA EL LIMITE" if total <= limite_pais else "PASA EL LIMITE"
                }
                
                with st.spinner("1/3 Mejorando redacción del borrador..."):
                    from text_processor import mejorar_redaccion
                    resolucion_limpia = mejorar_redaccion(resolucion) if resolucion.strip() else "Sin resolución proporcionada."
                
                if resolucion_limpia:
                    st.info("Texto mejorado por IA:\n" + resolucion_limpia)
                    with st.spinner("2/3 Guardando en Google Sheets..."):
                        from google_services import registrar_en_sheet, generar_documento_postmortem
                        exito_sheet = registrar_en_sheet(datos_finales, resolucion_limpia)
                        
                    if exito_sheet:
                        st.success("✅ Datos registrados en Google Sheets.")
                        with st.spinner("3/3 Generando Google Doc..."):
                            doc_link = generar_documento_postmortem(datos_finales, resolucion_limpia)
                        
                        if doc_link:
                            st.success("✅ ¡Proceso completado con éxito!")
                            st.markdown(f"📄 **Documento generado:** [Abrir Postmortem en Google Docs]({doc_link})")
                            st.balloons()

if __name__ == "__main__":
    if check_login():
        main()