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

    with st.sidebar:
        st.markdown("## 📊 Métricas de Operación")
        try:
            with st.spinner("Cargando métricas..."):
                from google_services import obtener_metricas_registro
                docs, acciones = obtener_metricas_registro()
                c1, c2 = st.columns(2)
                c1.metric("Documentos", docs)
                c2.metric("Acciones", acciones)
        except Exception as e:
            st.warning("No se pudo cargar el contador.")
            
        # Panel de Administrador
        from config import ADMIN_USERS
        if st.session_state.get("user_email") in ADMIN_USERS:
            st.divider()
            st.markdown("### 🛠️ Panel de Administrador")
            if st.button("♻️ Purgar Caché del Sistema", help="Limpia la memoria temporal de las tablas de Google Sheets y fuerza una recarga de datos frescos."):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Caché purgado correctamente.")
                
            if st.button("🧹 Limpiar Sesión Actual", help="Reinicia todos los formularios y borra imágenes de la memoria actual para empezar un caso nuevo."):
                email_save = st.session_state.get("user_email")
                st.session_state.clear()
                if email_save: st.session_state["user_email"] = email_save
                st.rerun()

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
            from google_services import obtener_limites_pais, obtener_reglas_influencer_v2
            limites_dict = obtener_limites_pais()
            reglas_influencer = obtener_reglas_influencer_v2()
            
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
            # Si el valor inicial no está en las opciones, dejamos el predeterminado
            opciones_fraude = ["", "Cliente fraude", "Falso positivo", "Cliente no fraude"]
            idx_fraude = 0
            for i, opt in enumerate(opciones_fraude):
                if opt.lower() == fraude_init.lower():
                    idx_fraude = i
                    break
            fraude = st.selectbox("FRAUDE", options=opciones_fraude, index=idx_fraude)
            
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
                    
                    # Mapear red social a abreviaturas de la tabla (fb, instagram, tw)
                    if "face" in val_red or "fb" in val_red: red_mapped = "fb"
                    elif "insta" in val_red or "ig" in val_red: red_mapped = "instagram"
                    elif "tw" in val_red or "x" in val_red: red_mapped = "tw"
                    else: red_mapped = val_red
                    
                    pais_lower = str(pais).strip().lower()
                    reglas_pais = reglas_influencer.get(pais_lower, {})
                    minimo_req = reglas_pais.get(red_mapped, None)
                    
                    if minimo_req is not None:
                        if cant_seguidores >= minimo_req:
                            st.success(f"✅ CUMPLE REQUISITO: Para {pais_lower.title()}, la red {red_mapped.upper()} requiere mínimo {minimo_req} seguidores. El usuario tiene {cant_seguidores}.")
                        else:
                            st.error(f"❌ NO CUMPLE: Para {pais_lower.title()}, la red {red_mapped.upper()} requiere mínimo {minimo_req} seguidores. El usuario solo tiene {cant_seguidores}.")
                    else:
                        st.warning(f"⚠️ No se encontraron reglas para el país '{pais_lower}' o la red '{red_mapped}'.")
                        st.info(f"DEBUG INTERNO - Paises en el sheet: {list(reglas_influencer.keys())}")
                except ValueError:
                    st.warning("⚠️ No se pudo leer la cantidad numérica de seguidores. Revisa el campo SEGUIDORES.")
            
            st.divider()
            st.markdown("### Cálculo para Devolución")
            
            monto_pedido_val = float(d.get("monto_pedido", 0.0))
            propina_val = float(d.get("propina", 0.0))
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                monto_pedido = st.number_input("PEDIDO ($)", value=monto_pedido_val, step=1.0)
            with col_m2:
                propina = st.number_input("PROPINA ($)", value=propina_val, step=1.0)
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
            
            st.markdown(f"**Subtotal (Devolución + Propina):** ${subtotal_1:.2f}")
            compensacion = st.number_input("COMPENSACION PROYECTADA ($)", value=float(subtotal_1), step=1.0)
            
            total = subtotal_1 + compensacion
            
            col_met1, col_met2 = st.columns(2)
            with col_met1: st.metric("LÍMITE PAÍS", f"${limite_pais:.2f}")
            with col_met2: st.metric("TOTAL DE SUMAS", f"${total:.2f}")
            
            if limite_pais > 0:
                if total > limite_pais:
                    st.error(f"🔴 Pasa el límite país (El total ${total:.2f} supera el límite de ${limite_pais:.2f})")
                else:
                    st.success(f"🟢 No pasa el límite país (Total: ${total:.2f})")
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
                    "evaluacion_limite": "no PASA EL LIMITE" if total <= limite_pais else "PASA EL LIMITE",
                    "user_email": st.session_state.get("user_email", "")
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
                
                st.divider()
                st.markdown("### 📸 Carga de Imágenes para Documento")
                st.info("Sube las imágenes correspondientes para inyectarlas directamente en el Google Doc.")
                
                col_img1, col_img2 = st.columns(2)
                with col_img1:
                    img_slack = st.file_uploader("Captura Slack", type=['png', 'jpg', 'jpeg'])
                    img_tablero = st.file_uploader("Tablero Operacional", type=['png', 'jpg', 'jpeg'])
                with col_img2:
                    form_gestion = st.file_uploader("Formulario Gestión", type=['png', 'jpg', 'jpeg'])
                
                img_devo, img_compen, form_devo = None, None, None
                if dfin['monto_devolucion'] > 0 or dfin['propina'] > 0:
                    st.markdown("**Imágenes de Devolución/Compensación**")
                    col_d1, col_d2, col_d3 = st.columns(3)
                    with col_d1: img_devo = st.file_uploader("Imagen Devolución", type=['png', 'jpg', 'jpeg'])
                    with col_d2: img_compen = st.file_uploader("Imagen Compensación", type=['png', 'jpg', 'jpeg'])
                    with col_d3: form_devo = st.file_uploader("Formulario Devolución", type=['png', 'jpg', 'jpeg'])
                    
                form_amenaza = None
                if dfin['is_amenaza']:
                    st.markdown("**Imagen de Amenaza**")
                    form_amenaza = st.file_uploader("Formulario Amenaza de Denuncia", type=['png', 'jpg', 'jpeg'])
                    
                form_wl = None
                if dfin['is_fraude']:
                    st.markdown("**Imagen Fraude (WL)**")
                    form_wl = st.file_uploader("Formulario WL", type=['png', 'jpg', 'jpeg'])
                
                imagenes_docs = {
                    "{{CAPTURA SLACK}}": img_slack,
                    "{{TABLERO_OPERACIONAL}}": img_tablero,
                    "{{IMAGEN_DEVO}}": img_devo,
                    "{{IMAGEN_COMPEN}}": img_compen,
                    "{{FORM_DEVO}}": form_devo,
                    "{{FORM_AMENAZA}}": form_amenaza,
                    "{{FORM_WL}}": form_wl,
                    "{{FORM_GESTION}}": form_gestion
                }
                
                if st.button("Aprobar y Generar Documento", type="primary"):
                    if not st.session_state.get("doc_generado_flag"):
                        with st.spinner("Guardando en Google Sheets..."):
                            from google_services import registrar_en_sheet
                            exito_sheet = registrar_en_sheet(dfin, res_final)
                            if exito_sheet:
                                st.success("✅ Registro guardado exitosamente en la pestaña REGISTRO del Google Sheet corporativo.")
                        
                        with st.spinner("Generando documento e inyectando imágenes... (Esto puede tomar 1 minuto)"):
                            from google_services import generar_documento_postmortem
                            doc_link = generar_documento_postmortem(dfin, rep_final, ana_final, res_final, imagenes_docs)
                            if doc_link:
                                st.session_state["doc_generado_flag"] = True
                                st.success(f"📄 ¡Documento generado con éxito! [Abrir Google Doc]({doc_link})")
                                st.balloons()
                                mostrar_listas(dfin)
                    else:
                        st.success("✅ Este documento ya fue generado y registrado exitosamente en esta sesión.")
                        mostrar_listas(dfin)
            else:
                st.subheader("Generación de Listas Internas")
                if not st.session_state.get("accionar_generado_flag"):
                    with st.spinner("Guardando registro básico en Google Sheets..."):
                        from google_services import registrar_en_sheet
                        exito_sheet = registrar_en_sheet(dfin, "SOLO ACCIONAR")
                        if exito_sheet:
                            st.session_state["accionar_generado_flag"] = True
                            st.success("✅ Registro guardado exitosamente en la pestaña REGISTRO del Google Sheet corporativo.")
                    st.success("📄 ¡Datos guardados! Revisa las listas abajo.")
                else:
                    st.success("✅ Registro guardado exitosamente. Revisa las listas abajo.")
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
    
    c3, c4 = st.columns(2)
    c3.markdown("**HORA INGRESO SLACK**")
    c3.code(dfin['hora'], language="text")
    c4.markdown("**TERMINO DE ACCION**")
    c4.code(dfin['fin_accion'], language="text")
    
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
