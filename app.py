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
            with st.spinner("Analizando las imágenes..."):
                imagenes_pil = [Image.open(f) for f in uploaded_files]
                
                from gemini_api import extraer_datos_gemini
                datos = extraer_datos_gemini(imagenes_pil)
                
                if datos:
                    # Pasamos el tiempo deducido directamente al fin de acción
                    datos["fin_accion"] = datos.get("ultima_interaccion", "")
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
                
                # Manejo seguro en caso de que Gemini devuelva null (None) o 'Revisar'
                val_seguidores = d.get("seguidores", "no corresponde")
                if val_seguidores is None:
                    val_seguidores = "no corresponde"
                
                # Si el modelo devuelve 'revisar', asume que no es influencer por defecto
                es_influencer = str(val_seguidores).strip().lower() not in ["no corresponde", "revisar", "null", "none", "", "-"]
                
                with col1:
                    caso_nro = st.text_input("CASO #", value=d.get("numero_caso", ""))
                    hora = st.text_input("HORA", value=d.get("hora", ""))
                    fin_accion = st.text_input("FIN DE ACCION", value=d.get("fin_accion", ""))
                    caso = st.text_input("CASO", value=d.get("caso", ""))
                    agente = st.text_input("AGENTE", value=d.get("agente_escala", ""))
                    if es_influencer:
                        red_social = st.text_input("RED SOCIAL", value=d.get("red_social", ""))
                    else:
                        red_social = "no corresponde"
                
                with col2:
                    correo = st.text_input("CORREO", value=d.get("correo", ""))
                    pedido_link = st.text_input("LINK PEDIDO", value=d.get("pedido_link", ""))
                    order_id = st.text_input("ORDER ID", value=d.get("order_id", ""))
                    user_id = st.text_input("USER ID", value=d.get("user_id", "Colocar"))
                    pais = st.text_input("PAIS", value=d.get("pais", ""))
                    if es_influencer:
                        seguidores = st.text_input("SEGUIDORES", value=d.get("seguidores", ""))
                    else:
                        seguidores = "no corresponde"
                
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
                                st.success(f"✅ CUMPLE REQUISITO: La red social {red_social} requiere mínimo {minimo_req} seguidores. El usuario tiene {cant_seguidores}.")
                            else:
                                st.error(f"❌ NO CUMPLE: La red social {red_social} requiere mínimo {minimo_req} seguidores. El usuario solo tiene {cant_seguidores}.")
                        else:
                            st.warning(f"⚠️ No se encontró la red social '{red_social}' en el catálogo de reglas (Opciones válidas: {', '.join(reglas_influencer.keys())}).")
                    except ValueError:
                        st.warning("⚠️ No se pudo leer la cantidad numérica de seguidores. Revisa el campo SEGUIDORES.")
                
                st.divider()
                st.markdown("### Cálculo para Devolución")
                
                # Campos de entrada de montos
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    monto_pedido = st.number_input("PEDIDO ($)", value=float(d.get("monto_pedido", 0.0)), step=1.0)
                with col_m2:
                    devolucion = st.number_input("DEVOLUCION ($)", value=float(d.get("monto_devolucion", 0.0)), step=1.0)
                
                # Búsqueda robusta de límite por país (case-insensitive)
                pais_lower = str(pais).strip().lower()
                limite_pais = 0.0
                for p_name, p_lim in limites_dict.items():
                    if p_name.strip().lower() == pais_lower:
                        limite_pais = float(p_lim)
                        break
                
                # Lógica matemática de compensación y límite
                comp_proyectada = monto_pedido
                total_proyectado = monto_pedido + comp_proyectada
                
                if limite_pais > 0:
                    if monto_pedido > limite_pais:
                        compensacion = 0.0
                    elif total_proyectado > limite_pais:
                        compensacion = limite_pais - monto_pedido
                    else:
                        compensacion = comp_proyectada
                else:
                    compensacion = comp_proyectada
                
                total = monto_pedido + compensacion
                
                st.write("") # Espaciador
                
                # Layout visual solicitado (Métricas lado a lado)
                col_met1, col_met2, col_met3 = st.columns(3)
                with col_met1:
                    st.metric("LÍMITE PAÍS", f"${limite_pais:.2f}")
                with col_met2:
                    st.metric("DEVOLUCIÓN", f"${devolucion:.2f}")
                with col_met3:
                    st.metric("COMPENSACIÓN FINAL", f"${compensacion:.2f}")
                
                # Semáforo de advertencia
                if limite_pais > 0:
                    if total >= limite_pais or monto_pedido > limite_pais:
                        st.error(f"🔴 PASA EL LÍMITE (Total proyectado: ${total_proyectado:.2f} | Se ajustó compensación para límite de ${limite_pais:.2f})")
                    else:
                        st.success(f"🟢 NO PASA EL LÍMITE (Total: ${total:.2f})")
                else:
                    st.warning(f"🟡 País sin límite configurado (Total: ${total:.2f})")

                st.divider()
                st.markdown("### Corrección de Estilo (Borrador de Resolución)")
                reporte_cliente = st.text_area("1. El cliente / líder reporta:", height=80, placeholder="Escribe aquí lo que reporta el cliente...")
                analisis_caso = st.text_area("2. Análisis del caso que se hizo:", height=80, placeholder="Escribe aquí tu análisis del caso...")
                resolucion_caso = st.text_area("3. Resolución del caso:", height=80, placeholder="Escribe aquí cómo se resolvió...")
                
                submit = st.form_submit_button("Aprobar Datos y Continuar", type="primary")

            if submit:
                # 1. Reunir los datos finales (con posibles ediciones manuales)
                datos_finales = {
                    "numero_caso": caso_nro,
                    "caso": caso,
                    "hora": hora,
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
                    "numeros": d.get("numeros", ""),
                    "fraude_operacional": d.get("fraude_operacional", ""),
                    "fraude_fintech": d.get("fraude_fintech", ""),
                    "seguidores": seguidores,
                    "contactos": d.get("contactos", ""),
                    "limite": limite_pais,
                    "evaluacion_limite": "no PASA EL LIMITE" if total <= limite_pais else "PASA EL LIMITE"
                }
                
                with st.spinner("Mejorando redacción del borrador..."):
                    from text_processor import mejorar_redaccion
                    if reporte_cliente.strip() or analisis_caso.strip() or resolucion_caso.strip():
                        resolucion_limpia = mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais)
                    else:
                        resolucion_limpia = "Sin resolución proporcionada."
                
                if resolucion_limpia:
                    st.success("✅ Proceso completado con éxito. Aquí está el texto mejorado:")
                    st.markdown("### Borrador Final Mejorado")
                    st.info(resolucion_limpia)
                    
                    # Funcionalidad futura guardada para cuando se active la automatización a Sheets/Docs
                    # with st.spinner("Guardando en Google Sheets..."):
                    #     from google_services import registrar_en_sheet, generar_documento_postmortem
                    #     exito_sheet = registrar_en_sheet(datos_finales, resolucion_limpia)
                    # if exito_sheet:
                    #     with st.spinner("Generando Google Doc..."):
                    #         doc_link = generar_documento_postmortem(datos_finales, resolucion_limpia)
                    #     if doc_link:
                    #         st.balloons()

if __name__ == "__main__":
    if check_login():
        main()