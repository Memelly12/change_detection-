from pydantic import BaseModel
from typing import List

# Modèle pour une image radar soumise
class RadarImageInfo(BaseModel):
    startDate: str
    endDate: str
    polarisation: str
    smoothing: int = 50  # Valeur par défaut pour le rayon de lissage
