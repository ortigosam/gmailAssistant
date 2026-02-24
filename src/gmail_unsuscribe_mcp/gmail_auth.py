"""
Modulo de autenticación para con Gmail API usando OAuth 2.0.
 Proporciona funciones para obtener credenciales de autenticación y
   crear un servicio de Gmail API para interactuar con la cuenta de Gmail del usuario.

   Flujo de autenticacion:
   1. si existe token.json -> Lo carga y lo usa (sesión previa)
   2. Si el token ha expirado -> Lo refresca automáticamente.
   3. Si no hay token -> Abre el navegador para que el usuario autorice
   4. Guarda el token en token.json para futuras ejecuciones.
"""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes = permisos que pedimos al usuario para acceder a su cuenta de Gmail
# Si cambias los scopes, debes borrar token.json para que se vuelva a solicitar autorización con los nuevos permisos.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify']

# Rutas a los archivos de credenciales y token
# Se guardan en el mismo directorio que el proyecto
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
CREDENTIALS_FILE = PROJECT_DIR / 'credentials.json'
TOKEN_FILE = PROJECT_DIR / 'token.json'

def get_credentials() -> Credentials:
    """Obtiene las credenciales de autenticación para Gmail API.
    Si ya existe un token válido, lo carga. Si el token ha expirado, lo refresca.
    Si no hay token, inicia el flujo de autorización para obtener uno nuevo.
    """
    creds = None
    # Paso 1: ¿Existe un token guardado de una sesion anterior?
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # Paso 2: ¿Las credenciales son válidas?
    if creds and creds.valid:
        return creds

    # Paso 3: ¿ El token expiró pero se puede refrescar?
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        # Paso 4: No hay token o no se puede refrescar -> Iniciar flujo de autorización
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(f"Archivo de credenciales no encontrado: {CREDENTIALS_FILE} "
                                    "Descarga credenciales desde Google Cloud Console y guárdalas "
                                    "como credentials.json en el directorio del proyecto.")
        # InstalledAppFlow gestiona todo el flujo OAuth para apps de escritorio:
        # - Abre el navegador para que el usuario inicie sesión y autorice la app.
        # - Recibe el código de autorización y lo intercambia por un token de acceso.
        # - Intercambia el codigo de autorizacion por un token
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
        # port=0 -> asigna un puerto libre automáticamente
    
    # Paso 5: Guarda el token para futuras ejecuciones
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())

    return creds

def get_gmail_service() :
    """
    Crea y devuelve un cliente de la Gmail API autenticado
    
    Este es el objeto principal que usaremos para interactuar con Gmail.
    Ejemplo de uso:
    service = get_gmail_service()
    results = service.users().messages().list(userId='me').
    Returns:
    Resources: Cliente de la gmail API    
    """
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    return service

def _smoke_tests(service) -> None:
    """Pequeña prueba para ver que autentica bien"""
    profile = service.users().getProfile(userId="me").execute()
    print("Authenticated as:", profile.get("emailAddress"))
    print("Messages total:", profile.get("messagesTotal"))

if __name__ == "__main__":
    svc = get_gmail_service()
    _smoke_tests(svc)