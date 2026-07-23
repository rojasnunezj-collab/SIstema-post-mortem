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

def mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais):
    """
    Toma los tres textos crudos del analista y los reescribe con tono ejecutivo, 
    aplicando reglas estrictas de sinonimia y limpieza.
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini.")
        return None
        
    try:
        genai.configure(api_key=api_key.strip())
    except Exception as e:
        st.error(f"❌ Error API: {e}")
        return None
        
    modelo_seguro = obtener_modelo_valido(api_key.strip())
    
    if not modelo_seguro:
        st.error("❌ Ningún modelo en tu API Key funcionó.")
        return None
        
    regla_wallet = "pedidos ya pagos" if pais.strip().lower() == "argentina" else "wallet o billetera"
    
    prompt = f"""Reescribe y une los 3 textos en español en 3 párrafos limpios.

REGLAS:
- Orden: Reporte, Análisis, Resolución.
- Sin muletillas.
- Devoluciones = "reintegro" o "reembolso".
- Intercala: "cliente" y "usuario".
- Cupón = "cupo" o "voucher".
- Billetera = "{regla_wallet}".
- NO inventes datos.

[TEXTO ORIGINAL]
Reporte: {reporte_cliente}
Análisis: {analisis_caso}
Resolución: {resolucion_caso}

[TEXTO MEJORADO (SOLO LOS 3 PARRAFOS, SIN INTRODUCCIONES, DIRECTO AL GRANO)]:
"""
    
    try:
        model = genai.GenerativeModel(modelo_seguro)
        
        # Sistema de reintentos para evadir errores 500 internos de Google
        import time
        response = None
        for intento in range(3):
            try:
                # Usar configuración de generación para acelerar la IA (baja temperatura y límite de tokens)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=800
                    )
                )
                break
            except Exception as sub_e:
                if "500" in str(sub_e) or "429" in str(sub_e):
                    if intento < 2:
                        time.sleep(2)
                        continue
                raise sub_e
                
        if not response:
            raise Exception("No se pudo obtener respuesta tras múltiples reintentos.")
        
        texto_limpio = response.text.replace("*Interleaving check:*", "").replace("```markdown", "").replace("```", "").replace("<FINAL>", "").replace("</FINAL>", "").strip()
        
        # Eliminar cualquier pensamiento inicial que deje la IA por accidente antes del texto real
        import re
        texto_limpio = re.sub(r'^(?:C\s*\(.*?\).*?Perfect\.?\s*)', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        texto_limpio = re.sub(r'^.*?Interleaving.*?:\s*', '', texto_limpio, flags=re.IGNORECASE | re.DOTALL)
        
        return texto_limpio.strip()
            
    except Exception as e:
        st.error(f"❌ Error al mejorar la redacción con IA: {e}")
        return None