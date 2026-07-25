# app.py
import streamlit as st
from PIL import Image

from config import LIMITES_PAIS
from auth import check_login
from gemini_api import extraer_datos_gemini

st.set_page_config(page_title="Sistema Postmortem | Operaciones Digitales", page_icon="📋", layout="wide")

def main():
    from config import ADMIN_USERS
    
    user_email = st.session_state.get('user_email', '')
    es_admin = user_email in ADMIN_USERS

    st.sidebar.title("Menú")
    st.sidebar.write(f"👤 Usuario: {user_email}")
    if st.sidebar.button("Cerrar Sesión"):
         st.session_state["logged_in"] = False
         st.rerun()
         
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
        
    st.sidebar.divider()
    if st.sidebar.button("🔄 Empezar Nuevo Caso (Limpiar Todo)"):
        # Limpiar todas las variables de la sesión del caso actual
        for key in list(st.session_state.keys()):
            if key not in ["logged_in", "user_email", "uploader_key"]:
                del st.session_state[key]
        st.session_state.uploader_key += 1 # Resetea físicamente las imágenes subidas
        st.rerun()

    if es_admin:
        st.sidebar.divider()
        st.sidebar.subheader("🛠️ Panel de Administrador")
        with st.sidebar.expander("Opciones de Admin", expanded=True):
            if st.button("Purgar Caché Global"):
                st.cache_data.clear()
                st.success("Caché limpiada correctamente.")
            
            with st.spinner("Contando..."):
                from google_services import obtener_cantidad_documentos
                cant_docs = obtener_cantidad_documentos()
                st.metric("Documentos Generados", cant_docs)

    st.title("Generador Automático de Postmortems")
    st.write("Sube las capturas del caso para extraer la información.")

    uploaded_files = st.file_uploader("Sube las capturas de pantalla", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

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
            
            st.markdown("### Datos Extraídos")
            col1, col2 = st.columns(2)
            
            with col1:
                caso_nro = st.text_input("CASO #", value=d.get("numero_caso", ""))
                hora = st.text_input("HORA", value=d.get("hora", ""))
                fin_accion = st.text_input("FIN DE ACCION", value=d.get("fin_accion", "Revisar"))
                caso = st.text_input("CASO", value=d.get("caso", ""))
                agente = st.text_input("AGENTE", value=d.get("agente_escala", ""))
                
                val_seguidores = d.get("seguidores", "no corresponde")
                if val_seguidores is None: val_seguidores = "no corresponde"
                import re
                es_influencer = bool(re.search(r'\d', str(val_seguidores)))
                
                if es_influencer:
                    red_social = st.text_input("RED SOCIAL", value=d.get("red_social", ""))
                else:
                    red_social = "no corresponde"

            with col2:
                correo = st.text_input("CORREO", value=d.get("correo", ""))
                pedido_link = st.text_input("LINK PEDIDO", value=d.get("pedido_link", ""))
                order_id = st.text_input("ORDER ID", value=d.get("order_id", ""))
                user_id = st.text_input("USER ID", value=d.get("user_id", "Revisar"))
                pais = st.text_input("PAIS", value=d.get("pais", ""))
                telefono = st.text_input("TELEFONO", value=d.get("telefono", "Revisar"))
                if es_influencer:
                    seguidores = st.text_input("SEGUIDORES", value=d.get("seguidores", ""))
                else:
                    seguidores = "no corresponde"
            
            fraude_init = f"{d.get('fraude_operacional', '')} {d.get('fraude_fintech', '')}".strip()
            fraude = st.text_input("FRAUDE (Recomendación: 'cliente fraude', 'fraude confirmado', 'cliente no fraude')", value=fraude_init)
            
            problema = st.text_area("PROBLEMA", value=d.get("motivo_reclamo", ""), height=80)
            ccr3 = st.text_input("CCR3", value=d.get("ccr3", ""))
            
            # Validación Influencer
            val_seguidores_str = str(seguidores).strip().lower()
            val_red = str(red_social).strip().lower()
            if val_seguidores_str and val_seguidores_str != "no corresponde" and val_red and val_red != "no corresponde":
                st.divider()
                st.markdown("### Validación de Influencer")
                try:
                    cant_seguidores = int(''.join(filter(str.isdigit, val_seguidores_str)))
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
            
            monto_pedido_val = float(d.get("monto_pedido", 0.0))
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                monto_pedido = st.number_input("PEDIDO ($)", value=monto_pedido_val, step=1.0)
            with col_m2:
                propina = st.number_input("PROPINA ($)", value=0.0, step=1.0)
            with col_m3:
                devolucion = st.number_input("DEVOLUCION ($)", value=monto_pedido_val, step=1.0)
            
            # Math lógica
            pais_lower = str(pais).strip().lower()
            limite_pais = 0.0
            for p_name, p_lim in limites_dict.items():
                if p_name.strip().lower() == pais_lower:
                    limite_pais = float(p_lim)
                    break
                    
            subtotal_1 = devolucion + propina
            comp_proyectada = subtotal_1
            total_proyectado = subtotal_1 + comp_proyectada
            
            if limite_pais > 0:
                if subtotal_1 > limite_pais:
                    compensacion = 0.0
                elif total_proyectado > limite_pais:
                    compensacion = limite_pais - subtotal_1
                else:
                    compensacion = comp_proyectada
            else:
                compensacion = comp_proyectada
                
            total = subtotal_1 + compensacion
            
            col_met1, col_met2, col_met3 = st.columns(3)
            with col_met1: st.metric("Devo + Propina", f"${subtotal_1:.2f}")
            with col_met2: st.metric("COMPENSACIÓN FINAL", f"${compensacion:.2f}")
            with col_met3: st.metric("LÍMITE PAÍS", f"${limite_pais:.2f}")
            
            if limite_pais > 0:
                if total >= limite_pais or subtotal_1 > limite_pais:
                    st.error(f"🔴 PASA EL LÍMITE (Total proyectado: ${total_proyectado:.2f} | Se ajustó compensación para límite de ${limite_pais:.2f})")
                else:
                    st.success(f"🟢 NO PASA EL LÍMITE (Total: ${total:.2f})")
            else:
                st.warning(f"🟡 País sin límite configurado (Total: ${total:.2f})")
            
            st.divider()
            st.markdown("### Formularios Adicionales")
            is_fraude = st.checkbox("¿El caso involucra Fraude (WL)?", value=False)
            caso_str = str(caso).strip().lower()
            is_amenaza = "amenaza" in caso_str or "denuncia" in caso_str
            if is_amenaza:
                st.info("⚠️ La IA detectó una Amenaza de Denuncia en el tipo de CASO.")
            
            st.divider()
            
            tipo_proceso = st.radio("¿Qué acción vas a realizar?", ["Postmortem Completo (Mejorar texto y Google Doc)", "Solo Accionar (Generar Listas Internas)"])
            
            reporte_cliente = ""
            analisis_caso = ""
            resolucion_caso = ""
            if "Postmortem Completo" in tipo_proceso:
                st.markdown("### Corrección de Estilo (Borrador de Resolución)")
                reporte_cliente = st.text_area("1. El cliente / líder reporta:", height=80, placeholder="Escribe aquí lo que reporta el cliente...")
                analisis_caso = st.text_area("2. Análisis del caso que se hizo:", height=80, placeholder="Escribe aquí tu análisis del caso...")
                resolucion_caso = st.text_area("3. Resolución del caso:", height=80, placeholder="Escribe aquí cómo se resolvió...")
                label_btn = "Mejorar Textos y Continuar"
            else:
                label_btn = "Generar Listas de Accionar"
            
            if st.button(label_btn, type="primary"):
                # Save data to session
                st.session_state["datos_finales"] = {
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
                    "propina": propina,
                    "compensacion": compensacion,
                    "total": total,
                    "numeros": d.get("numeros", ""),
                    "telefono": telefono,
                    "fraude_str": fraude,
                    "is_fraude": is_fraude,
                    "is_amenaza": is_amenaza,
                    "es_influencer": es_influencer,
                    "seguidores": seguidores,
                    "contactos": d.get("contactos", ""),
                    "limite": limite_pais,
                    "evaluacion_limite": "no PASA EL LIMITE" if total <= limite_pais else "PASA EL LIMITE"
                }
                st.session_state["tipo_proceso"] = tipo_proceso
                st.session_state["borrador"] = (reporte_cliente, analisis_caso, resolucion_caso)
                
                if "Postmortem Completo" in tipo_proceso:
                    with st.spinner("Mejorando redacción del borrador..."):
                        from text_processor import mejorar_redaccion
                        if reporte_cliente.strip() or analisis_caso.strip() or resolucion_caso.strip():
                            rep_limpio, ana_limpio, res_limpia = mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais)
                        else:
                            rep_limpio, ana_limpio, res_limpia = "", "", ""
                        st.session_state["textos_mejorados"] = (rep_limpio, ana_limpio, res_limpia)
                
                st.session_state["step"] = 2
                st.rerun()

        if st.session_state.get("step") == 2:
            st.divider()
            dfin = st.session_state["datos_finales"]
            tipo = st.session_state["tipo_proceso"]
            
            if "Postmortem Completo" in tipo:
                st.subheader("Revisión Final de Textos")
                rep_limpio, ana_limpio, res_limpia = st.session_state.get("textos_mejorados", ("", "", ""))
                rep_final = st.text_area("1. Reporte (Editado):", value=rep_limpio, height=150)
                ana_final = st.text_area("2. Análisis (Editado):", value=ana_limpio, height=150)
                res_final = st.text_area("3. Resolución (Editado):", value=res_limpia, height=150)
                
                if st.button("Aprobar y Generar Documento", type="primary"):
                    # Registro siempre (incluso si está vacío)
                    with st.spinner("Guardando en Google Sheets..."):
                        from google_services import registrar_en_sheet
                        exito_sheet = registrar_en_sheet(dfin, res_final)
                        if exito_sheet:
                            st.success("✅ Registro guardado exitosamente en la pestaña REGISTRO del Google Sheet corporativo.")
                    
                    with st.spinner("Generando documento de Google Docs..."):
                        from google_services import generar_documento_postmortem
                        doc_link = generar_documento_postmortem(dfin, rep_final, ana_final, res_final)
                        if doc_link:
                            st.success(f"📄 ¡Documento generado con éxito! [Abrir Google Doc]({doc_link})")
                            st.balloons()
                            mostrar_listas(dfin)
            else:
                st.subheader("Generación de Listas Internas")
                with st.spinner("Guardando registro básico en Google Sheets..."):
                    from google_services import registrar_en_sheet
                    exito_sheet = registrar_en_sheet(dfin, "SOLO ACCIONAR")
                    if exito_sheet:
                        st.success("✅ Registro guardado en Google Sheets.")
                st.success("📄 ¡Datos guardados! Revisa las listas abajo.")
                st.balloons()
                mostrar_listas(dfin)

def mostrar_listas(dfin):
    st.divider()
    st.subheader("📋 Datos para Formularios Internos")
    
    st.markdown("### Gestión Diaria")
    c1, c2 = st.columns(2)
    c1.markdown("**CASO#**")
    c1.code(dfin['numero_caso'], language="text")
    c2.markdown("**CASO**")
    c2.code(dfin['caso'], language="text")
    
    if dfin['es_influencer'] or dfin['is_amenaza'] or dfin['monto_devolucion'] > 0:
        st.divider()
        st.markdown("### Devolución")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("**USER ID**")
        c1.code(dfin['user_id'], language="text")
        c2.markdown("**ORDER ID**")
        c2.code(dfin['order_id'], language="text")
        c3.markdown("**PAIS**")
        c3.code(dfin['pais'], language="text")
        c4.markdown("**AGENTE**")
        c4.code(dfin['agente_escala'], language="text")
        
        c5, c6, c7 = st.columns(3)
        c5.markdown("**DEVOLUCION**")
        c5.code(dfin['monto_devolucion'], language="text")
        c6.markdown("**PROPINA**")
        c6.code(dfin['propina'], language="text")
        c7.markdown("**COMPENSACION FINAL**")
        c7.code(dfin['compensacion'], language="text")
        
        st.markdown("**LINK**")
        st.code(dfin['pedido_link'], language="text")
    
    if dfin['is_fraude']:
        st.divider()
        st.markdown("### Fraude (WL)")
        fraude_val = dfin['fraude_str']
        if not fraude_val: fraude_val = "Sí"
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("**CORREO**")
        c1.code(dfin['correo'], language="text")
        c2.markdown("**USER ID**")
        c2.code(dfin['user_id'], language="text")
        c3.markdown("**ORDER ID**")
        c3.code(dfin['order_id'], language="text")
        c4.markdown("**PAIS**")
        c4.code(dfin['pais'], language="text")
        
        st.markdown("**FRAUDE**")
        st.code(fraude_val, language="text")
        
    if dfin['is_amenaza']:
        st.divider()
        st.markdown("### Amenaza de Denuncia")
        c1, c2, c3 = st.columns(3)
        c1.markdown("**USER ID**")
        c1.code(dfin['user_id'], language="text")
        c2.markdown("**CORREO**")
        c2.code(dfin['correo'], language="text")
        c3.markdown("**PAIS**")
        c3.code(dfin['pais'], language="text")

if __name__ == "__main__":
    if check_login():
        main()
