# text_processor.py
import os
import streamlit as st
import google.generativeai as genai

def obtener_modelo_valido(api_key):
    if "modelo_gemini_cache" in st.session_state:
        return st.session_state["modelo_gemini_cache"]

    msg_placeholder = st.empty()
    msg_placeholder.info("⏳ Buscando IA disponible...")
    
    priority_list = [
        "models/gemini-3-flash-preview",
        "models/gemini-3.1-flash-lite-preview",
        "models/gemini-3.1-flash-lite",
        "models/gemini-2.5-flash-lite",
        "models/gemini-flash-lite-latest",
        "models/nano-banana-pro-preview"
    ]
    
    genai.configure(api_key=api_key.strip())
    
    for model_name in priority_list:
        try:
            model = genai.GenerativeModel(model_name)
            model.generate_content("test")
            st.session_state["modelo_gemini_cache"] = model_name
            msg_placeholder.empty()
            return model_name
        except Exception:
            continue
            
    msg_placeholder.empty()
    st.session_state["modelo_gemini_cache"] = priority_list[0]
    return priority_list[0]

def mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais):
    """
    Reescribe las 3 secciones utilizando una única llamada con JSON Schema forzado.
    Retorna una tupla de 4 strings: (reporte, analisis, resolucion, warning_msg).
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "AIzaSyB77IabSlG2eo8_w99_bMbplnrPCynV-Ik"))
    
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini.")
        return reporte_cliente, analisis_caso, resolucion_caso, "API Key no encontrada."
        
    try:
        genai.configure(api_key=api_key.strip())
    except Exception as e:
        st.error(f"❌ Error API: {e}")
        return reporte_cliente, analisis_caso, resolucion_caso, str(e)
        
    modelo_seguro = obtener_modelo_valido(api_key.strip())
    
    if not modelo_seguro:
        st.error("❌ Ningún modelo en tu API Key funcionó.")
        return reporte_cliente, analisis_caso, resolucion_caso, "Error validando el modelo."
        
    regla_wallet = "pedidos ya pagos" if pais.strip().lower() == "argentina" else "wallet o billetera"
    
    prompt = f"""
Reescribe los siguientes textos (Reporte, Análisis, Resolución) para un documento oficial de Postmortem de atención al cliente.

OBJETIVO:
El texto resultante debe ser sumamente corporativo, analítico, profesional, y con ortografía perfecta. 

REGLAS DE ESTILO (¡OBLIGATORIO!):
1. Eres un formateador puro. Tu única tarea es mejorar y reescribir los textos. NUNCA devuelvas el texto original sin cambios a menos que ya sea perfecto.
2. NUNCA empieces los párrafos con frases repetitivas como "Tras revisar", "Al verificar", "Se procede a", o "Tras realizar la revisión". Usa variedad y ve directo al grano (ej: "Se identificó...", "El usuario indicó...", "El sistema muestra...").
3. Evita redundancias. Si el texto original repite lo mismo, condénsalo en un texto claro y potente.
4. Vocabulario Obligatorio: Usa "reintegro" o "reembolso", "cupo" o "voucher". Llama a la billetera virtual del cliente exactamente como: "{regla_wallet}". Alterna entre los términos "cliente" y "usuario" para enriquecer la lectura.
5. NO inventes datos, fechas, motivos ni montos que no estén en el texto original.
6. Mantén la objetividad absoluta: no uses lenguaje emocional ("lamentablemente", "desafortunadamente", "por suerte").

TEXTOS A REESCRIBIR (MEJÓRALOS OBLIGATORIAMENTE):
[Reporte]: {reporte_cliente}
[Análisis]: {analisis_caso}
[Resolución]: {resolucion_caso}

IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido. El JSON debe tener exactamente estas claves:
"reporte_editado", "analisis_editado", "resolucion_editado".
No agregues comentarios ni comillas invertidas fuera del JSON.
"""
    
    import time
    import json
    
    model = genai.GenerativeModel(modelo_seguro)
    for intento in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1, 
                    max_output_tokens=2048,
                    response_mime_type="application/json"
                )
            )
            
            try:
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
            except ValueError:
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA no pudo generar el texto (posible bloqueo por seguridad o formato)."
                
            start = raw_text.find('{')
            if start != -1:
                raw_text = raw_text[start:]
                end = raw_text.rfind('}')
                if end != -1:
                    datos = json.loads(raw_text[:end+1], strict=False)
                else:
                    return reporte_cliente, analisis_caso, resolucion_caso, "El formato JSON quedó incompleto (sin cierre)."
            else:
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA no devolvió un JSON válido."
                
            # Validar que realmente haya hecho cambios y no haya devuelto los originales o un JSON vacío
            if not datos.get("reporte_editado"):
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA devolvió campos vacíos, se usaron los originales."
            return datos.get("reporte_editado", ""), datos.get("analisis_editado", ""), datos.get("resolucion_editado", ""), None
        except Exception as e:
            if "modelo_gemini_cache" in st.session_state:
                del st.session_state["modelo_gemini_cache"]
            error_msg = str(e)
            if "500" in error_msg or "429" in error_msg or "Quota" in error_msg:
                if intento < 2:
                    time.sleep(2)
                    continue
                if "429" in error_msg or "Quota" in error_msg:
                    return reporte_cliente, analisis_caso, resolucion_caso, f"⚠️ Bloqueo de cuota de IA. Detalle: {error_msg}"
            return reporte_cliente, analisis_caso, resolucion_caso, f"Error del mejorador: {error_msg}"
            
    return reporte_cliente, analisis_caso, resolucion_caso, "No se pudo mejorar el texto después de varios intentos."