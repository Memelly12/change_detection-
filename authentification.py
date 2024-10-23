import ee
import json
from google.oauth2 import service_account

def initialize_earth_engine():
    # Charger les informations du compte de service
    service_account_info = json.load(open('ee-memelelie123-129a4524a0a8.json'))

    # Définir les scopes corrects pour Google Earth Engine
    scopes = ['https://www.googleapis.com/auth/earthengine.readonly']

    # Créer des identifiants basés sur le compte de service avec les scopes
    credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=scopes)

    # Initialiser Earth Engine avec ces identifiants
    ee.Initialize(credentials)

initialize_earth_engine()
