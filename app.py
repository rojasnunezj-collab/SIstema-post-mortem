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
            
        st.divider()
        if st.button("🧹 Liberar Espacio del Bot", help="Vacía la papelera interna de la cuenta de servicio si se llenó la cuota."):
            try:
                with st.spinner("Liberando espacio..."):
                    from google_services import get_credentials
                    from googleapiclient.discovery import build
                    creds = get_credentials()
                    if creds:
                        drive_service = build('drive', 'v3', credentials=creds)
                        # Empty trash
                        drive_service.files().emptyTrash().execute()
                        # Also delete old docs owned by bot if necessary, but empty trash is safer first.
                        st.success("¡Papelera del bot vaciada con éxito!")
            except Exception as e:
                st.error(f"Error al limpiar: {e}")
            
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
    
    opciones_proceso = ["Postmortem Completo (Mejorar texto y Google Doc)", "Solo Accionar (Generar Listas Internas)"]
    
    if "tipo_proceso_global" not in st.session_state:
        st.session_state["tipo_proceso_global"] = None
        
    idx = None
    if st.session_state["tipo_proceso_global"] is not None:
        idx = opciones_proceso.index(st.session_state["tipo_proceso_global"])
        
    seleccion = st.radio(
        "¿Qué acción vas a realizar?", 
        opciones_proceso, 
        index=idx, 
        disabled=(idx is not None)
    )
    
    if seleccion is not None and st.session_state["tipo_proceso_global"] is None:
        st.session_state["tipo_proceso_global"] = seleccion
        st.rerun()
        
    tipo_proceso = st.session_state["tipo_proceso_global"]

    uploaded_files = []
    if tipo_proceso is not None:
        st.write("Sube las capturas del caso para extraer la información.")
        uploaded_files = st.file_uploader("Sube las capturas de pantalla", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

        if uploaded_files:
            cols = st.columns(len(uploaded_files))
            for i, file in enumerate(uploaded_files):
                image = Image.open(file)
                cols[i].image(image, caption=file.name, use_container_width=True)

        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Extraer Datos (Gemini AI)", type="primary", use_container_width=True):
                if not uploaded_files:
                    st.warning("⚠️ Sube al menos una imagen para usar la extracción automática.")
                else:
                    with st.spinner("Analizando las imágenes..."):
                        imagenes_pil = [Image.open(f) for f in uploaded_files]
                        
                        from gemini_api import extraer_datos_gemini
                        datos = extraer_datos_gemini(imagenes_pil)
                        
                        if datos:
                            # Pasamos el tiempo deducido directamente al fin de acción
                            datos["fin_accion"] = datos.get("ultima_interaccion", "")
                            st.session_state["datos_extraidos"] = datos
                            st.session_state["modo_manual"] = False
                            st.success("✅ ¡Datos extraídos con éxito!")
                        
        with col_btn2:
            if st.button("Llenado Manual (Post de Guru)", type="secondary", use_container_width=True):
                st.session_state["datos_extraidos"] = {}
                st.session_state["modo_manual"] = True
                st.success("📝 Modo manual activado. Puedes llenar los campos a continuación.")
        
        if "datos_extraidos" in st.session_state:
            st.subheader("Auditoría de Datos y Cálculos")
            tipo_proceso = st.session_state.tipo_proceso_global
            d = st.session_state["datos_extraidos"]
            
            # Obtener limites y reglas dinámicas
            from google_services import obtener_limites_pais, obtener_reglas_influencer_v2
            limites_dict = obtener_limites_pais()
            reglas_influencer = obtener_reglas_influencer_v2()
            
            st.markdown("### Datos Extraídos")
            col1, col2 = st.columns(2)
            
            with col1:
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
                    
                numeros = st.text_input("NÚMEROS DE CONTACTO", value=d.get("numeros", ""))

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
                    
                contactos = d.get("contactos", "")
            
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
            
            def safe_float(val):
                try:
                    if val is None or str(val).strip() == "":
                        return 0.0
                    return float(str(val).replace(',', '.').replace('$', '').strip())
                except ValueError:
                    return 0.0

            monto_pedido_val = safe_float(d.get("monto_pedido", 0.0))
            propina_val = safe_float(d.get("propina", 0.0))
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
                    
            pedido_mas_propina = monto_pedido + propina
            
            st.markdown(f"**Subtotal (Pedido + Propina):** ${pedido_mas_propina:.2f}")
            
            compensacion_ideal = pedido_mas_propina
            if limite_pais > 0:
                max_comp_permitida = max(0.0, limite_pais - pedido_mas_propina)
                compensacion_sugerida = min(compensacion_ideal, max_comp_permitida)
            else:
                compensacion_sugerida = compensacion_ideal
                
            compensacion = st.number_input("COMPENSACION PROYECTADA ($)", value=float(compensacion_sugerida), step=1.0)
            
            total = pedido_mas_propina + compensacion
            
            col_met1, col_met2 = st.columns(2)
            with col_met1: st.metric("LÍMITE PAÍS", f"${limite_pais:.2f}")
            with col_met2: st.metric("PEDIDO+PROPINA + COMPENSACIÓN", f"${total:.2f}")
            
            if limite_pais > 0:
                if total > limite_pais:
                    st.error(f"🔴 Pasa el límite país (El total ${total:.2f} supera el límite de ${limite_pais:.2f})")
                else:
                    st.success(f"🟢 No pasa el límite país (Total: ${total:.2f})")
            else:
                st.warning(f"🟡 País sin límite configurado (Total: ${total:.2f})")
            
            if "Postmortem Completo" in tipo_proceso:
                st.divider()
                st.markdown("**3. Resolución del caso (Métodos y Fechas):**")
                
                from datetime import datetime, timedelta
                default_date = datetime.today() + timedelta(days=30)
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    op_dev = st.selectbox("Método de Devolución", ["Ninguna", "Tarjeta de débito", "Tarjeta de crédito", "Tarjeta prepago", "Cupón", "Wallet"])
                with col_d2:
                    f_dev = None
                    if op_dev in ["Cupón", "Wallet"]:
                        f_dev = st.date_input("Fecha de vigencia (Devolución)", format="DD/MM/YYYY", value=default_date)
                        
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    op_comp = st.selectbox("Método de Compensación", ["Ninguna", "Cupón", "Wallet"])
                with col_c2:
                    f_comp = None
                    if op_comp in ["Cupón", "Wallet"]:
                        f_comp = st.date_input("Fecha de vigencia (Compensación)", format="DD/MM/YYYY", value=default_date)
                        
                opciones_otras = ["WL", "Baja de servicio", "Desactivación de cuenta", "Tk jira"]
                otras_seleccionadas = st.multiselect("Otras Gestiones (opcional)", opciones_otras)
                
                # Armar los textos finales
                def armar_texto(monto, opcion, fecha):
                    if opcion == "Ninguna" or monto == 0:
                        return f"${monto}"
                    if opcion in ["Tarjeta de débito", "Tarjeta de crédito", "Tarjeta prepago"]:
                        return f"${monto} (se verá reflejado en su {opcion.lower()} en máximo 7 días hábiles)"
                    elif opcion in ["Cupón", "Wallet"]:
                        fecha_str = fecha.strftime("%d/%m/%Y") if fecha else "xx/xx/xxxx"
                        return f"${monto} (se verá reflejado como {opcion.lower()} con vigencia hasta {fecha_str})"
                    return f"${monto}"
                    
                devolucion_str = armar_texto(devolucion, op_dev, f_dev)
                compensacion_str = armar_texto(compensacion, op_comp, f_comp)
                otras_gestiones_str = "𝗢𝘁𝗿𝗮𝘀 𝗴𝗲𝘀𝘁𝗶𝗼𝗻𝗲𝘀: " + "/".join(otras_seleccionadas) if otras_seleccionadas else ""
            else:
                devolucion_str = f"${devolucion}"
                compensacion_str = f"${compensacion}"
                otras_gestiones_str = ""
            
            fraude_str_lower = fraude.lower()
            is_fraude = "cliente fraude" in fraude_str_lower or "falso positivo" in fraude_str_lower
            
            contacto_guru = ""
            if st.session_state.get("modo_manual", False):
                st.divider()
                st.markdown("### Llenado Manual Gurú")
                contacto_guru = st.text_area("Detalle de contacto Gurú", placeholder="Escribe aquí el detalle de gurú...", height=80)
                
            caso_str = str(caso).strip().lower()
            is_amenaza = "amenaza" in caso_str or "denuncia" in caso_str
            if is_amenaza:
                st.info("⚠️ La IA detectó una Amenaza de Denuncia en el tipo de CASO.")
            
            st.divider()
            
            reporte_cliente = ""
            analisis_caso = ""
            resolucion_caso = ""
            if "Postmortem Completo" in tipo_proceso:
                st.markdown("### Corrección de Estilo (Borrador de Resolución)")
                reporte_cliente = st.text_area("1. El cliente / líder reporta:", height=80, placeholder="Escribe aquí lo que reporta el cliente...")
                analisis_caso = st.text_area("2. Análisis del caso que se hizo:", height=80, placeholder="Escribe aquí tu análisis del caso...")
                resolucion_caso = st.text_area("3. Resolución del caso (Explicación adicional):", height=80, placeholder="Escribe aquí cómo se resolvió de forma narrativa...")
                
                label_btn = "Mejorar Textos y Continuar"
            else:
                label_btn = "Generar Listas de Accionar"
            
            if st.button(label_btn, type="primary"):
                # Save data to session
                st.session_state["datos_finales"] = {
                    "numero_caso": d.get("numero_caso", ""),
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
                    "devolucion_str": devolucion_str if "Postmortem Completo" in tipo_proceso else f"${devolucion}",
                    "propina": propina,
                    "compensacion": compensacion,
                    "compensacion_str": compensacion_str if "Postmortem Completo" in tipo_proceso else f"${compensacion}",
                    "otras_gestiones": otras_gestiones_str if "Postmortem Completo" in tipo_proceso else "",
                    "numeros": numeros,
                    "telefono": telefono,
                    "is_fraude": is_fraude,
                    "is_amenaza": is_amenaza,
                    "fraude_str": fraude,
                    "es_influencer": es_influencer,
                    "seguidores": seguidores,
                    "contactos": contactos,
                    "contacto_guru": contacto_guru,
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
                            resultado_mejora = mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais)
                            if len(resultado_mejora) == 4:
                                rep_limpio, ana_limpio, res_limpia, warning_msg = resultado_mejora
                            else:
                                rep_limpio, ana_limpio, res_limpia = resultado_mejora[:3]
                                warning_msg = None
                                
                            if warning_msg:
                                st.session_state["warning_mejora"] = warning_msg
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
                if "warning_mejora" in st.session_state:
                    st.warning(st.session_state["warning_mejora"])
                    
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
                
                st.markdown("**Imágenes de Devolución/Compensación**")
                col_d1, col_d2, col_d3 = st.columns(3)
                with col_d1: img_devo = st.file_uploader("Imagen Devolución", type=['png', 'jpg', 'jpeg'])
                with col_d2: img_compen = st.file_uploader("Imagen Compensación", type=['png', 'jpg', 'jpeg'])
                with col_d3: form_devo = st.file_uploader("Formulario Devolución", type=['png', 'jpg', 'jpeg'])
                
                with st.expander("Imágenes Adicionales"):
                    col_e1, col_e2, col_e3 = st.columns(3)
                    with col_e1: extra_1 = st.file_uploader("Extra 1", type=['png', 'jpg', 'jpeg'])
                    with col_e2: extra_2 = st.file_uploader("Extra 2", type=['png', 'jpg', 'jpeg'])
                    with col_e3: extra_3 = st.file_uploader("Extra 3", type=['png', 'jpg', 'jpeg'])
                
                if dfin.get("is_amenaza"):
                    st.markdown("**Imagen de Amenaza (Opcional)**")
                    form_amenaza = st.file_uploader("Formulario Amenaza de Denuncia", type=['png', 'jpg', 'jpeg'])
                else:
                    form_amenaza = None
                    
                if dfin.get("is_fraude"):
                    st.markdown("**Imagen Fraude (WL) (Opcional)**")
                    form_wl = st.file_uploader("Formulario WL", type=['png', 'jpg', 'jpeg'])
                else:
                    form_wl = None
                
                st.divider()
                if "datos_finales" in st.session_state:
                    mostrar_listas_toggle = st.checkbox("Mostrar datos para formularios internos", value=True)
                    if mostrar_listas_toggle:
                        mostrar_listas(st.session_state["datos_finales"])
                        
                # --- NUEVA SECCIÓN DE CONTACTOS ---
                st.divider()
                st.markdown("### 📞 Detalle de Contactos (Interacciones)")
                incluir_contactos = st.checkbox("Incluir contactos en el documento", value=True)
                
                datos_contactos = []
                if incluir_contactos:
                    try:
                        def_contactos = int(str(dfin.get("numeros", "1")).strip())
                    except ValueError:
                        def_contactos = 1
                        
                    cantidad_contactos = st.number_input("NÚMERO DE CONTACTOS", min_value=0, max_value=10, value=def_contactos)
                    
                    from google_services import obtener_criterios_evaluacion
                    from gemini_api import evaluar_interaccion_gemini
                    
                    comunicacion_data, gestion_data = obtener_criterios_evaluacion()
                    
                    for i in range(1, int(cantidad_contactos) + 1):
                        with st.expander(f"Contacto #{i}", expanded=True):
                            st.markdown("**Datos Generales de Interacción**")
                            col_c3, col_c4 = st.columns(2)
                            with col_c3:
                                fecha_c = st.text_input(f"Fecha y hora (C{i})", key=f"fecha_c{i}")
                            with col_c4:
                                link_c = st.text_input(f"Link HeroCare (C{i})", key=f"link_c{i}")
                            
                            st.markdown("**Agentes Involucrados en este Contacto**")
                            num_agentes_key = f"num_ag_c{i}"
                            if num_agentes_key not in st.session_state:
                                st.session_state[num_agentes_key] = 1
                                
                            agentes_list = []
                            for j in range(st.session_state[num_agentes_key]):
                                col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
                                with col_c1:
                                    agente_c = st.text_input(f"Agente {j+1}", key=f"agente_c{i}_{j}")
                                
                                is_bot = "bot" in agente_c.lower()
                                
                                if not is_bot:
                                    with col_c2:
                                        area_c = st.text_input(f"Área", key=f"area_c{i}_{j}")
                                    with col_c3:
                                        sop_c = st.radio(f"SOP", ["Siguió SOP", "No siguió SOP"], key=f"sop_c{i}_{j}", horizontal=True, label_visibility="collapsed")
                                else:
                                    area_c = "N/A"
                                    sop_c = "N/A"
                                
                                agentes_list.append({"agente": agente_c, "area": area_c, "sop": sop_c})
                                
                            if st.button(f"➕ Añadir otro Agente al Contacto {i}", key=f"add_ag_{i}"):
                                st.session_state[num_agentes_key] += 1
                                st.rerun()
                                
                            # Armar string de agentes combinados para la variable
                            agentes_str_parts = []
                            for ag in agentes_list:
                                nombre = ag["agente"].strip() if ag["agente"].strip() else "Desconocido"
                                area = ag["area"].strip() if ag["area"].strip() else "Sin área"
                                sop = ag["sop"]
                                agentes_str_parts.append(f"{nombre} - {area} - {sop}")
                            agentes_info = ", ".join(agentes_str_parts)
                            
                            st.markdown("**Análisis y Transcripción**")
                            transcripcion = st.text_area(f"Transcripción del chat (C{i})", height=150, key=f"transc_c{i}")
                            
                            if st.button(f"Analizar Interacción C{i}", key=f"btn_analizar_c{i}"):
                                if transcripcion:
                                    with st.spinner("Analizando con Gemini..."):
                                        # Le pasamos todos los agentes para que los evalúe
                                        resultado = evaluar_interaccion_gemini(transcripcion, comunicacion_data, gestion_data, agentes_info)
                                        st.session_state[f"om_c{i}"] = resultado
                                        if "resumen" in resultado:
                                            st.session_state[f"resumen_c{i}"] = resultado["resumen"]
                                else:
                                    st.warning("Pega la transcripción para analizar.")
                            
                            om_data = st.session_state.get(f"om_c{i}", {})
                            
                            if f"resumen_c{i}" in st.session_state:
                                st.info("Resumen generado:")
                                resumen_texto = st.text_area("Texto resumido a inyectar", value=st.session_state[f"resumen_c{i}"], height=100, key=f"resumen_input_{i}")
                            else:
                                resumen_texto = transcripcion
                                
                            is_bot = "bot" in agentes_info.lower()
                            
                            if not is_bot:
                                col_om1, col_om2, col_om3, col_om4 = st.columns(4)
                                with col_om1:
                                    om1 = st.text_area(f"OM1 (C{i})", value=om_data.get("om1") or "", key=f"om1_c{i}")
                                with col_om2:
                                    om2 = st.text_area(f"OM2 (C{i})", value=om_data.get("om2") or "", key=f"om2_c{i}")
                                with col_om3:
                                    om3 = st.text_area(f"OM3 (C{i})", value=om_data.get("om3") or "", key=f"om3_c{i}")
                                with col_om4:
                                    om4 = st.text_area(f"OM4 (C{i})", value=om_data.get("om4") or "", key=f"om4_c{i}")
                            else:
                                om1 = ""
                                om2 = ""
                                om3 = ""
                                om4 = ""
                                
                            st.markdown(f"**Imágenes del Contacto {i}**")
                            col_img_c1, col_img_c2, col_img_c3, col_img_c4 = st.columns(4)
                            img1 = col_img_c1.file_uploader(f"Imagen 1 (C{i})", type=['png', 'jpg', 'jpeg'], key=f"img1_c{i}")
                            img2 = col_img_c2.file_uploader(f"Imagen 2 (C{i})", type=['png', 'jpg', 'jpeg'], key=f"img2_c{i}")
                            img3 = col_img_c3.file_uploader(f"Imagen 3 (C{i})", type=['png', 'jpg', 'jpeg'], key=f"img3_c{i}")
                            img4 = col_img_c4.file_uploader(f"Imagen 4 (C{i})", type=['png', 'jpg', 'jpeg'], key=f"img4_c{i}")
                            
                            contacto = {
                                "fecha": fecha_c.replace('.', '/'),
                                "agentes_info": agentes_info,
                                "link": link_c,
                                "om1": "" if om1.strip().lower() == "no aplica" else om1.strip(),
                                "om2": "" if om2.strip().lower() == "no aplica" else om2.strip(),
                                "om3": "" if om3.strip().lower() == "no aplica" else om3.strip(),
                                "om4": "" if om4.strip().lower() == "no aplica" else om4.strip(),
                                "descripcion": resumen_texto,
                                "img1": img1,
                                "img2": img2,
                                "img3": img3,
                                "img4": img4
                            }
                            datos_contactos.append(contacto)
                        
                st.session_state["datos_finales"]["cantidad_contactos"] = cantidad_contactos if incluir_contactos else 0
                st.session_state["datos_finales"]["con_sin"] = "CONTACTOS" if incluir_contactos and cantidad_contactos > 0 else "SIN CONTACTOS"
                # ------------------------------------
                
                imagenes_docs = {
                    "{{CAPTURA SLACK}}": img_slack,
                    "{{TABLERO_OPERACIONAL}}": img_tablero,
                    "{{IMAGEN_DEVO}}": img_devo,
                    "{{IMAGEN_COMPEN}}": img_compen,
                    "{{FORM_DEVO}}": form_devo,
                    "{{FORM_AMENAZA}}": form_amenaza,
                    "{{FORM_WL}}": form_wl,
                    "{{FORM_GESTION}}": form_gestion,
                    "{{EXTRA_1}}": extra_1,
                    "{{EXTRA_2}}": extra_2,
                    "{{EXTRA_3}}": extra_3
                }
                
                # Inyectar las imágenes de los contactos
                for idx, c_data in enumerate(datos_contactos):
                    i = idx + 1
                    imagenes_docs[f"{{{{IMAGEN_CONTACTO1_{i}}}}}"] = c_data["img1"]
                    imagenes_docs[f"{{{{IMAGEN_CONTACTO2_{i}}}}}"] = c_data["img2"]
                    imagenes_docs[f"{{{{IMAGEN_CONTACTO3_{i}}}}}"] = c_data["img3"]
                    imagenes_docs[f"{{{{IMAGEN_CONTACTO4_{i}}}}}"] = c_data["img4"]
                
                if st.button("Aprobar y Generar Documento", type="primary"):
                    if not st.session_state.get("doc_generado_flag"):
                        try:
                            with st.spinner("Guardando en Google Sheets..."):
                                from google_services import registrar_en_sheet
                                exito_sheet = registrar_en_sheet(dfin, res_final)
                                if exito_sheet:
                                    st.success("✅ Registro guardado exitosamente en la pestaña REGISTRO del Google Sheet corporativo.")
                        except Exception as e:
                            st.error(f"Error guardando en Sheet: {e}")
                        
                        try:
                            with st.spinner("Generando documento e inyectando imágenes... (Esto puede tomar 1 minuto)"):
                                from google_services import generar_documento_postmortem
                                doc_link = generar_documento_postmortem(
                                    dfin, rep_final, ana_final, res_final, 
                                    imagenes_docs=imagenes_docs, 
                                    datos_contactos=datos_contactos
                                )
                                if doc_link:
                                    st.session_state["doc_generado_flag"] = True
                                    st.success(f"📄 ¡Documento generado con éxito! [Abrir Google Doc]({doc_link})")
                                    st.balloons()
                                else:
                                    st.warning("⚠️ No se pudo generar el documento por el error de almacenamiento, pero tus datos sí fueron procesados.")
                        except Exception as e:
                            st.error(f"Fallo crítico al generar documento: {e}")
                            
                        # Siempre mostrar las listas generadas, falle o no el documento
                        st.divider()
                        st.markdown("### 📥 Descarga Manual (Contingencia)")
                        from datetime import datetime
                        texto_contingencia = f"""# Postmortem Caso {dfin.get("caso", "")}

**Fecha:** {datetime.now().strftime("%d/%m/%Y")}
**CCR3:** {dfin.get("ccr3", "")}
**Motivo de Reclamo:** {dfin.get("motivo_reclamo", "")}
**Monto Devolución:** ${dfin.get('monto_devolucion', 0)}
**Compensación Final:** ${dfin.get('compensacion', 0)}
**Order ID:** {dfin.get("order_id", "")}
**User ID:** {dfin.get("user_id", "")}
**Correo:** {dfin.get("correo", "")}
**Link Pedido:** {dfin.get("pedido_link", "")}
**Agente Escala:** {dfin.get("agente_escala", "")}
**Cliente Fraude:** {dfin.get("fraude_str", "")}
**Número Teléfono:** {dfin.get("telefono", "")}

---
## DETALLES DE CONTACTOS:"""
                        for i, c_data in enumerate(datos_contactos, 1):
                            texto_contingencia += f"""
### Contacto #{i}
**Fecha:** {c_data.get("fecha", "")}
**Agente:** {c_data.get("agente", "")} ({c_data.get("area", "")})
**Link Hero:** {c_data.get("link", "")}
**OM1:** {c_data.get("om1", "")}
**OM2:** {c_data.get("om2", "")}
**OM3:** {c_data.get("om3", "")}
**OM4:** {c_data.get("om4", "")}
**Descripción:** {c_data.get("descripcion", "")}"""

                        texto_contingencia += f"""
---
## Reporte del Cliente
{rep_final}

## Análisis del Problema
{ana_final}

## Resolución / Accionables
{res_final}
"""                     
                        st.download_button(
                            label="Descargar Texto del Documento (Backup)",
                            data=texto_contingencia,
                            file_name=f"Postmortem_{dfin.get('numero_caso', 'S_N')}.txt",
                            mime="text/plain",
                            type="secondary"
                        )
                        
                    else:
                        st.success("✅ Este registro ya fue procesado exitosamente en esta sesión.")
            else:
                st.subheader("Generación de Listas Internas")
                if not st.session_state.get("accionar_generado_flag"):
                    with st.spinner("Guardando registro básico en Google Sheets..."):
                        from google_services import registrar_en_sheet
                        exito_sheet = registrar_en_sheet(dfin, "SOLO ACCIONAR")
                        if exito_sheet:
                            st.session_state["accionar_generado_flag"] = True
                            st.success("✅ Registro guardado exitosamente en la pestaña REGISTRO del Google Sheet corporativo.")
                    st.success("📄 ¡Datos guardados! Revisa las listas en la parte superior.")
                else:
                    st.success("✅ Registro guardado exitosamente. Revisa las listas en la parte superior.")
                
                # Show list automatically for "Solo Accionar"
                mostrar_listas(dfin)

def mostrar_listas(dfin):
    st.divider()
    st.subheader("📋 Datos para Formularios Internos")
    
    st.markdown("### Gestión Diaria")
    c1, c2 = st.columns(2)
    c1.markdown("**CASO**")
    c1.code(dfin['caso'], language="text")
    c2.markdown("**USER ID**")
    c2.code(dfin.get('user_id', ''), language="text")
    
    c4, c5 = st.columns(2)
    c4.markdown("**HORA INGRESO SLACK**")
    c4.code(dfin['hora'], language="text")
    c5.markdown("**TERMINO DE ACCION**")
    c5.code(dfin['fin_accion'], language="text")
    
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
