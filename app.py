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
            
            # Obtener limites y reglas dinámicas
            from google_services import obtener_limites_pais, obtener_reglas_influencer
            limites_dict = obtener_limites_pais()
            reglas_influencer = obtener_reglas_influencer()
            
            with st.form("form_postmortem"):
                # Organizamos los campos en el orden exacto solicitado
                col1, col2 = st.columns(2)
                
                with col1:
                    caso_nro = st.text_input("CASO #", value=d.get("numero_caso", ""))
                    hora = st.text_input("HORA", value=d.get("hora", ""))
                    fin_accion = st.text_input("FIN DE ACCION (Ingreso manual)", placeholder="Ej: 6:15 PM")
                    caso = st.text_input("CASO", value=d.get("caso", ""))
                    agente = st.text_input("AGENTE", value=d.get("agente_escala", ""))
                    red_social = st.text_input("RED SOCIAL", value=d.get("red_social", ""))
                
                with col2:
                    correo = st.text_input("CORREO", value=d.get("correo", ""))
                    pedido_link = st.text_input("LINK PEDIDO", value=d.get("pedido_link", ""))
                    order_id = st.text_input("ORDER ID", value=d.get("order_id", ""))
                    pais = st.text_input("PAIS", value=d.get("pais", ""))
                    seguidores = st.text_input("SEGUIDORES", value=d.get("seguidores", ""))
                
                problema = st.text_area("PROBLEMA", value=d.get("motivo_reclamo", ""), height=80)
                ccr3 = st.text_input("CCR3", value=d.get("ccr3", ""))
                
                # Validación de Influencer
                val_seguidores = str(seguidores).strip().lower()
                val_red = str(red_social).strip().lower()
                
                if val_seguidores and val_seguidores != "no corresponde" and val_red and val_red != "no corresponde":
                    st.divider()
                    st.markdown("### Validación de Influencer")
                    try:
                        cant_seguidores = int(''.join(filter(str.isdigit, val_seguidores)))
                        minimo_req = reglas_influencer.get(val_red, None)
                        
                        if minimo_req is not None:
                            if cant_seguidores >= minimo_req:
                                st.success(f"🌟 CUMPLE REQUISITO: La red social {red_social} requiere mínimo {minimo_req} seguidores. El usuario tiene {cant_seguidores}.")
                            else:
                                st.error(f"❌ NO CUMPLE: La red social {red_social} requiere mínimo {minimo_req} seguidores. El usuario solo tiene {cant_seguidores}.")
                        else:
                            st.warning(f"⚠️ No se encontró la red social '{red_social}' en el catálogo de reglas (Opciones válidas: {', '.join(reglas_influencer.keys())}).")
                    except ValueError:
                        st.warning("⚠️ No se pudo leer la cantidad numérica de seguidores. Revisa el campo SEGUIDORES.")
                
                st.divider()
                st.markdown("### Cálculos Financieros")
                
                # Montos
                monto_pedido_ia = float(d.get("monto_pedido", 0.0) if d.get("monto_pedido") else 0.0)
                monto_devolucion_ia = float(d.get("monto_devolucion", 0.0) if d.get("monto_devolucion") else 0.0)
                
                col3, col4 = st.columns(2)
                
                with col3:
                    pedido = st.number_input("PEDIDO ($)", min_value=0.0, value=monto_pedido_ia, step=10.0)
                    devolucion = st.number_input("DEVOLUCION ($)", min_value=0.0, value=monto_devolucion_ia, step=10.0)
                
                # Calcular límite basado en el país escrito
                limite_pais = limites_dict.get(pais.strip(), 0)
                
                # Logica financiera:
                # 1. Total (proyectado) = Pedido + Compensacion (que inicialmente es el pedido)
                # 2. Si Total > Limite, la compensacion se reduce a Limite - Pedido
                # 3. Si Pedido >= Limite, compensacion = 0
                if pedido >= limite_pais and limite_pais > 0:
                    compensacion = 0.0
                else:
                    compensacion_proyectada = pedido
                    if (pedido + compensacion_proyectada) > limite_pais and limite_pais > 0:
                        compensacion = limite_pais - pedido
                    else:
                        compensacion = compensacion_proyectada
                        
                total = pedido + compensacion
                
                with col4:
                    st.metric(f"LIMITE: $", f"{limite_pais:.2f}")
                    st.metric("COMPENSACION: $", f"{compensacion:.2f}")
                    
                    if limite_pais > 0:
                        if pedido > limite_pais:
                            st.error(f"TOTAL: ${total:.2f}, PASA EL LIMITE (El pedido por sí solo ya supera el límite)")
                        elif total >= limite_pais:
                            st.warning(f"TOTAL: ${total:.2f}, PASA EL LIMITE (Compensación ajustada automáticamente)")
                        else:
                            st.success(f"TOTAL: ${total:.2f}, NO PASA EL LIMITE")
                    else:
                        st.info(f"TOTAL: ${total:.2f} (País sin límite configurado)")

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