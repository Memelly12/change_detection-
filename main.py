from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import geemap
import ee
import os
from fastapi.responses import HTMLResponse
from authentification import initialize_earth_engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

initialize_earth_engine()

# Créer une instance de l'application FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="carte"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vous pouvez restreindre à l'URL de ngrok
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèle pour une image radar soumise
class RadarImageInfo(BaseModel):
    startDate: str
    endDate: str
    polarisation: str
    smoothing: int = 50  # Valeur par défaut pour le rayon de lissage

# Modèle pour la soumission de plusieurs images radar
class RadarImagesRequest(BaseModel):
    roi: dict  # ROI en GeoJSON
    images: List[RadarImageInfo]

# Fonction pour charger les images radar
def load_images(start_date: str, end_date: str, polarisation: str, roi_geojson):
    roi = ee.Geometry.Polygon(roi_geojson['coordinates'])
    
    image = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', polarisation)) \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .filterMetadata('resolution_meters', 'equals', 10) \
        .filterBounds(roi) \
        .select(polarisation) \
        .filterDate(start_date, end_date) \
        .median() \
        .clip(roi)
    
    return image

# Fonction pour corriger le bruit speckle
def speckle_correction(image, smoothing_radius=50):
    return image.focal_mean(smoothing_radius, 'circle', 'meters')

# Fonction pour calculer les différences entre deux images
def calculate_diff(image1, image2):
    return image1.subtract(image2)

# Fonction pour calculer les statistiques (moyenne, écart-type) sur la différence d'image
def calculate_stats(diff_image, roi, scale=10):
    reducers = ee.Reducer.mean().combine(
        reducer2=ee.Reducer.stdDev(),
        sharedInputs=True
    )
    stats = diff_image.reduceRegion(
        reducer=reducers,
        geometry=roi,
        scale=scale,
        maxPixels=1e8,  # ou 1e7 si 1e8 est trop grand
        bestEffort=True  # Ajout de bestEffort pour ajuster automatiquement
    ).getInfo()
    
    return stats


# Fonction pour appliquer les seuils de perte de végétation
def apply_threshold(diff_image, stats, polarisation):
    stdDev_key = f"{polarisation}_stdDev"
    mean_key = f"{polarisation}_mean"
    
    upper_threshold = (stats[stdDev_key] * 1.5) + stats[mean_key]
    thresholded_image = diff_image.gt(upper_threshold)
    return thresholded_image

@app.post("/generate-map/")
async def process_images(request: RadarImagesRequest):
    try:
        roi_geojson = request.roi
        roi = ee.Geometry.Polygon(roi_geojson['coordinates'])
        
        # Créer une carte geemap
        Map = geemap.Map()

        # Stocker les images traitées
        filtered_images = []
        vis_params = {
            'min': -27 if request.images[0].polarisation == 'VH' else -15,
            'max': 0
        }

        # Traiter chaque image radar (appliquer correction et ajouter à la carte)
        for radar_image in request.images:
            image = load_images(
                start_date=radar_image.startDate,
                end_date=radar_image.endDate,
                polarisation=radar_image.polarisation,
                roi_geojson=roi_geojson
            )
            filtered_image = speckle_correction(image, radar_image.smoothing)
            filtered_images.append((filtered_image, radar_image.polarisation, radar_image.startDate, radar_image.endDate))
            Map.addLayer(filtered_image, vis_params, f'{radar_image.polarisation} {radar_image.startDate} - {radar_image.endDate}')
        
        # Sauvegarder la carte dans un fichier HTML temporaire
        html_file = "carte/map_output.html"
        Map.to_html(filename=html_file, title="My Map", width="100%", height="880px")

        # Retourner le chemin de la carte
        return {"map_url": f"https://d8dc-154-68-54-21.ngrok-free.app/carte/{html_file}"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
