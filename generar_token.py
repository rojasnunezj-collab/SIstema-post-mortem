import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Los mismos permisos que usa tu aplicación
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

def main():
    print("Iniciando flujo OAuth...")
    print("Asegúrate de haber renombrado el archivo descargado de Google Cloud a 'credentials.json' y ponerlo en esta misma carpeta.")
    
    if not os.path.exists("credentials.json"):
        print("❌ ERROR: No se encontró el archivo 'credentials.json'. Por favor ponlo aquí antes de continuar.")
        return
        
    try:
        # Esto abrirá tu navegador web
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Guardar el token extraído en token.json
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
            
        print("\n✅ ¡ÉXITO! Se ha generado el archivo 'token.json'.")
        
    except Exception as e:
        print(f"❌ Error durante la autorización: {e}")

if __name__ == '__main__':
    main()
