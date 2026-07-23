# text_processor.py
import os
import streamlit as st
import google.generativeai as genai

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_modelo_valido(api_key):
    """Encuentra el mejor modelo disponible probando máximo 3 opciones para evitar el límite de cuota y evadir 404s."""
    genai.configure(api_key=api_key)
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception:
        modelos = ["models/gemini-1.5-flash", "models/gemini-pro"]

    # Excluir modelos experimentales o descontinuados que causan 404 (ej. 2.5, 3.6)
    modelos_seguros = [m for m in modelos if "2.5" not in m and "3.6" not in m]
    
    flash = [m for m in modelos_seguros if 'flash' in m.lower()]
    otros = [m for m in modelos_seguros if 'flash' not in m.lower()]
    
    # Solo probamos máximo 3 candidatos para NO agotar tu cuota de API por minuto
    candidatos = (flash[:2] + otros[:1]) if flash else otros[:3]
    
    if not candidatos:
        candidatos = ["models/gemini-pro"] # Fallback histórico indestructible
        
    for m in candidatos:
        try:
            model = genai.GenerativeModel(m)
            if model.generate_content("a"): # Prueba súper ligera
                return m
        except Exception:
            continue
            
    return candidatos[0]

def procesar_seccion(texto, tipo, regla_wallet, modelo_seguro):
    if not texto.strip():
        return ""
        
    prompt = f"""
Por favor, reescribe el siguiente texto sobre el {tipo} de forma corporativa.
Tu respuesta DEBE ser únicamente un (1) solo párrafo en español, sin viñetas, sin títulos, y sin análisis previo en inglés.

Aplica estas palabras clave de forma natural:
- Usa "reintegro" o "reembolso" (no devolución).
- Usa "cupo" o "voucher".
- Llama a la billetera virtual: "{regla_wallet}".
- Usa tanto la palabra "cliente" como "usuario".
No inventes datos ni montos.

Texto a reescribir:
{texto}
"""
    import time
    model = genai.GenerativeModel(modelo_seguro)
    for intento in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.1, max_output_tokens=600)
            )
            
            # Limpieza exhaustiva en caso de que la IA deje viñetas o palabras en inglés
            texto_final = response.text.replace("```markdown", "").replace("```", "").strip()
            import re
            texto_final = re.sub(r'^.*?(?:Output|Draft|Respuesta|Texto|Párrafo).*?:', '', texto_final, flags=re.IGNORECASE | re.DOTALL).strip()
            
            return texto_final
        except Exception as sub_e:
            if "500" in str(sub_e) or "429" in str(sub_e):
                if intento < 2:
                    time.sleep(2)
                    continue
            return texto # Fallback al texto original si falla la API
    return texto

def mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais):
    """
    Reescribe las 3 secciones usando multihilos para máxima velocidad y evitar alucinaciones.
    Retorna una tupla de 3 strings: (reporte, analisis, resolucion).
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini.")
        return reporte_cliente, analisis_caso, resolucion_caso
        
    try:
        genai.configure(api_key=api_key.strip())
    except Exception as e:
        st.error(f"❌ Error API: {e}")
        return reporte_cliente, analisis_caso, resolucion_caso
        
    modelo_seguro = obtener_modelo_valido(api_key.strip())
    
    if not modelo_seguro:
        st.error("❌ Ningún modelo en tu API Key funcionó.")
        return reporte_cliente, analisis_caso, resolucion_caso
        
    regla_wallet = "pedidos ya pagos" if pais.strip().lower() == "argentina" else "wallet o billetera"
    
    import concurrent.futures
    
    # Ejecutamos las 3 llamadas a la IA en paralelo (Reduce el tiempo de 30s a 10s)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_rep = executor.submit(procesar_seccion, reporte_cliente, "Reporte del Cliente", regla_wallet, modelo_seguro)
        f_ana = executor.submit(procesar_seccion, analisis_caso, "Análisis del Agente", regla_wallet, modelo_seguro)
        f_res = executor.submit(procesar_seccion, resolucion_caso, "Resolución del Caso", regla_wallet, modelo_seguro)
        
        rep = f_rep.result()
        ana = f_ana.result()
        res = f_res.result()
        
    return rep, ana, res