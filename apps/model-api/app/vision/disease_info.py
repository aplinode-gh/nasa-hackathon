"""Disease knowledge base: types, descriptions, and farmer-facing guidance.

Covers classes present in the vision training data plus common field diseases so
the API can explain detections in plain language.
"""
from __future__ import annotations

from typing import Any

# Canonical labels used by the vision classifier.
DISEASE_INFO: dict[str, dict[str, Any]] = {
    "healthy": {
        "disease_name": "Healthy leaf",
        "disease_type": "none",
        "crop": "general",
        "severity": "clear",
        "description": "No visible disease symptoms were detected on the leaf. Color and texture appear normal in the scanned area.",
        "causes": "No disease-causing pathogen or stress pattern detected in this image.",
        "steps": [
            "Continue regular field scouting and irrigation/nutrition management.",
            "Remove heavily damaged or old leaves to improve airflow.",
            "Re-scan if you notice new spots, yellowing, curling, or wilting.",
        ],
        "rescan_timing": "Rescan in 7-10 days or when new symptoms appear.",
        "caution": "A healthy-looking scan does not rule out early infection; monitor nearby plants.",
    },
    "leaf_rust": {
        "disease_name": "Leaf rust",
        "disease_type": "fungal",
        "crop": "wheat/maize/general",
        "severity": "treat_now",
        "description": "Leaf rust is a fungal disease that produces small reddish-brown to orange pustules (rust-like spots) on leaves, reducing photosynthesis and yield.",
        "causes": "Caused by rust fungi (e.g. Puccinia spp.). Favored by warm, humid weather, leaf wetness, dense canopy, and susceptible varieties.",
        "steps": [
            "Scout the field to estimate spread; mark affected patches.",
            "Remove and destroy heavily infected leaves where practical.",
            "Apply a recommended rust fungicide following local label rates and timing.",
            "Use resistant/tolerant varieties next season and avoid excess nitrogen.",
            "Improve airflow with proper spacing and timely irrigation.",
        ],
        "rescan_timing": "Rescan in 5-7 days to confirm spread is slowing.",
        "caution": "Wear protective equipment when applying chemicals and follow label instructions.",
    },
    "leaf_blight": {
        "disease_name": "Leaf blight",
        "disease_type": "fungal/bacterial",
        "crop": "general",
        "severity": "treat_now",
        "description": "Leaf blight causes rapid browning, lesions, or drying of leaf tissue, often starting at tips/edges or as expanding spots that merge.",
        "causes": "Can be caused by fungal or bacterial pathogens. Spread is favored by warm, wet conditions, splashing water/rain, infected residue, and poor airflow.",
        "steps": [
            "Remove and destroy badly infected leaves or plants to reduce inoculum.",
            "Avoid overhead irrigation late in the day; reduce leaf wetness duration.",
            "Improve drainage and spacing for airflow.",
            "Apply an appropriate fungicide/bactericide if symptoms are spreading (confirm locally).",
            "Rotate crops and clear infected crop residue after harvest.",
        ],
        "rescan_timing": "Rescan in 5-7 days.",
        "caution": "Do not compost infected material; confirm product choice for fungal vs bacterial blight locally.",
    },
    "powdery_mildew": {
        "disease_name": "Powdery mildew",
        "disease_type": "fungal",
        "crop": "general",
        "severity": "watch",
        "description": "Powdery mildew appears as white or gray powdery patches on leaf surfaces, which can reduce growth and photosynthesis if severe.",
        "causes": "Caused by various powdery mildew fungi. Favored by moderate temperatures, high humidity (without free water on leaves), shade, and dense foliage.",
        "steps": [
            "Improve airflow and sunlight penetration by spacing/pruning where possible.",
            "Avoid excess nitrogen fertilization.",
            "Apply sulfur or potassium-bicarbonate based treatments if pressure increases (per label).",
            "Remove heavily infected leaves early.",
        ],
        "rescan_timing": "Rescan in 7 days.",
        "caution": "Apply treatments in cooler hours; follow label rates to avoid phytotoxicity.",
    },
    "bacterial_spot": {
        "disease_name": "Bacterial spot",
        "disease_type": "bacterial",
        "crop": "tomato/pepper/general",
        "severity": "treat_now",
        "description": "Bacterial spot causes small, dark, water-soaked to necrotic spots on leaves that may merge and lead to leaf drop under severe infection.",
        "causes": "Caused by Xanthomonas species. Spread by contaminated seed/transplants, splashing rain/irrigation, tools, and warm wet conditions.",
        "steps": [
            "Remove and destroy severely affected plants/leaves; avoid working when foliage is wet.",
            "Use clean seed/transplants and sanitize tools.",
            "Improve airflow and avoid overhead irrigation.",
            "Copper-based bactericides may help reduce spread when used preventively/early (follow local guidance).",
        ],
        "rescan_timing": "Rescan in 5-7 days.",
        "caution": "Bacterial diseases are hard to cure once established; focus on limiting spread and sanitation.",
    },
    "leaf_curl": {
        "disease_name": "Leaf curl",
        "disease_type": "viral/physiological",
        "crop": "cotton/tomato/chili/general",
        "severity": "watch",
        "description": "Leaf curl shows upward/downward curling, thickening, or distortion of leaves, often with stunting or yellowing depending on cause.",
        "causes": "Often caused by viruses transmitted by whiteflies (e.g. leaf curl viruses), but can also result from herbicide injury, heat, or nutrient issues.",
        "steps": [
            "Inspect for whiteflies or other vectors; use yellow sticky traps for monitoring.",
            "Remove severely affected plants to reduce virus source if viral infection is suspected.",
            "Manage vectors with recommended integrated pest management practices.",
            "Avoid water/heat stress and verify no herbicide drift; correct nutrition if deficient.",
        ],
        "rescan_timing": "Rescan in 7-10 days and monitor nearby plants.",
        "caution": "There is no direct cure for viral leaf curl; controlling vectors and removing sources is key.",
    },
}


def explain(label: str, confidence: float | None = None, source: str = "vision_model") -> dict[str, Any]:
    key = (label or "").strip().lower().replace(" ", "_")
    info = DISEASE_INFO.get(key)
    if not info:
        # try fuzzy contains
        for k, v in DISEASE_INFO.items():
            if k in key or key in k:
                info = v
                key = k
                break
    if not info:
        info = {
            "disease_name": label or "Unknown condition",
            "disease_type": "unknown",
            "crop": "unknown",
            "severity": "watch",
            "description": "The model could not confidently match this image to a known disease class.",
            "causes": "Unclear from the provided image.",
            "steps": [
                "Take a clearer close-up photo of the affected leaf in good light.",
                "Compare with healthy leaves from the same crop.",
                "Consult a local extension officer for confirmation.",
            ],
            "rescan_timing": "Rescan with a clearer image.",
            "caution": "Avoid treatment until the condition is confirmed.",
        }
        key = (label or "unknown").strip().lower().replace(" ", "_") or "unknown"

    out = {
        "label": key,
        **info,
        "confidence": None if confidence is None else round(float(confidence), 4),
        "model_source": source,
    }
    return out


def list_diseases() -> list[dict[str, Any]]:
    return [explain(k) for k in DISEASE_INFO]
