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
        # Esto abrirá tu navegador web local
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        # Forzamos el consentimiento para que Google nos devuelva sí o sí un 'refresh_token'
        creds = flow.run_local_server(port=0, prompt='consent')
        
        # Leemos el credentials original para inyectar client_id y client_secret (por un bug de la librería)
        with open('credentials.json', 'r') as f:
            client_config = json.load(f)
            client_type = list(client_config.keys())[0]
            c_id = client_config[client_type]["client_id"]
            c_secret = client_config[client_type]["client_secret"]
            
        token_dict = json.loads(creds.to_json())
        token_dict["client_id"] = c_id
        token_dict["client_secret"] = c_secret
        
        # Guardar el token extraído en token.json
        with open('token.json', 'w') as token_file:
            json.dump(token_dict, token_file, indent=2)
            
        print("\n✅ ¡ÉXITO! Se ha generado el archivo 'token.json'.")
        
    except Exception as e:
        print(f"❌ Error durante la autorización: {e}")

if __name__ == '__main__':
    main()
