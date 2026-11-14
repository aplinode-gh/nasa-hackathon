"""Farm and activity constants."""

from __future__ import annotations

from datetime import datetime

CROPS = [
    "wheat", "cotton", "sugarcane", "maize", "rice",
    "barley", "mustard", "sunflower", "sesame", "peanut",
    "millet", "sorghum", "gram", "lentil", "mung bean",
    "onion", "potato", "tomato", "cauliflower", "cabbage",
    "carrot", "radish", "spinach", "okra", "chili",
    "cucumber", "watermelon", "muskmelon", "citrus", "mango",
    "banana", "apple", "grape", "olive", "date palm",
]

IRRIGATION_METHODS = ["drip", "sprinkler", "flood", "rainfed"]
SOIL_TYPES = ["clay", "loam", "sandy", "silt"]
RECORD_TYPES = ["sowing", "planting", "irrigation", "fertilizer", "pesticide", "disease", "harvest"]
SEASONS = ["Summer", "Winter", "Rainy", "Dry"]
WEATHER_CONDITIONS = ["Sunny", "Cloudy", "Rainy", "Stormy", "Snowy", "Fog"]

STAGE_SEQUENCES = {
    "wheat": ["Sowing", "Tillering", "Vegetative", "Grain filling", "Ready"],
    "cotton": ["Sowing", "Squaring", "Flowering", "Boll filling", "Ready"],
    "sugarcane": ["Sowing", "Tillering", "Grand growth", "Ripening", "Harvest"],
    "maize": ["Sowing", "Vegetative", "Tasselling", "Grain filling", "Ready"],
    "rice": ["Sowing", "Tillering", "Panicle initiation", "Grain filling", "Ready"],
}

DEFAULT_STAGE = "Sowing"
CURRENT_YEAR = datetime.now().year
YEAR_OPTIONS = [f"{start}-{str(start + 1)[-2:]}" for start in range(CURRENT_YEAR - 10, CURRENT_YEAR + 11)]
