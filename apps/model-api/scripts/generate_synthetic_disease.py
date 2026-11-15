import json
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

random.seed(42)
np.random.seed(42)

OUT = "datasets/vision/disease/raw"
CLASSES = {
    "healthy": {"base": (70, 150, 70), "lesion": None},
    "leaf_rust": {"base": (65, 130, 55), "lesion": (170, 90, 30)},
    "leaf_blight": {"base": (60, 120, 50), "lesion": (110, 95, 40)},
    "powdery_mildew": {"base": (75, 140, 65), "lesion": (225, 225, 215)},
    "bacterial_spot": {"base": (68, 135, 60), "lesion": (60, 45, 35)},
    "leaf_curl": {"base": (72, 128, 58), "lesion": (120, 150, 80)},
}


def main() -> None:
    manifest = []
    for label, spec in CLASSES.items():
        d = os.path.join(OUT, label)
        os.makedirs(d, exist_ok=True)
        for i in range(40):
            w = h = 256
            br, bg, bb = spec["base"]
            noise = np.random.randint(-18, 18, (h, w, 3), dtype=np.int16)
            base = np.zeros((h, w, 3), dtype=np.uint8)
            for c, v in enumerate([br, bg, bb]):
                base[:, :, c] = np.clip(v + noise[:, :, c], 0, 255).astype(np.uint8)
            img = Image.fromarray(base, "RGB")
            draw = ImageDraw.Draw(img)
            # veins
            for _ in range(6):
                x0 = w // 2 + random.randint(-12, 12)
                draw.line(
                    [(x0, 8), (w // 2 + random.randint(-45, 45), h - 8)],
                    fill=(min(255, br + 25), min(255, bg + 25), min(255, bb + 12)),
                    width=1,
                )
            if spec["lesion"]:
                lr, lg, lb = spec["lesion"]
                for _ in range(5 + (i % 5)):
                    cx = random.randint(28, w - 28)
                    cy = random.randint(28, h - 28)
                    rx = random.randint(5, 24)
                    ry = random.randint(5, 24)
                    color = (
                        int(np.clip(lr + random.randint(-20, 20), 0, 255)),
                        int(np.clip(lg + random.randint(-20, 20), 0, 255)),
                        int(np.clip(lb + random.randint(-20, 20), 0, 255)),
                    )
                    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=color)
                if label == "leaf_curl":
                    img = img.transform(
                        img.size,
                        Image.AFFINE,
                        (1, 0.08, -5, 0.02, 1, -3),
                        resample=getattr(Image, "Resampling", Image).BILINEAR,
                    )
            img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
            path = os.path.join(d, f"{label}_{i:03d}.jpg")
            img.save(path, "JPEG", quality=92)
            manifest.append({"label": label, "file": path, "bytes": os.path.getsize(path)})

    os.makedirs("datasets/vision/disease", exist_ok=True)
    with open("datasets/vision/disease/synthetic_manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "source": "synthetic_labeled_starter",
                "note": "Starter synthetic disease patterns for pipeline training; replace/augment with real labeled leaf images (e.g. PlantVillage/field photos) for production accuracy.",
                "classes": list(CLASSES.keys()),
                "total": len(manifest),
                "items": manifest,
            },
            f,
            indent=2,
        )
    print(f"generated {len(manifest)} images across {len(CLASSES)} classes")


if __name__ == "__main__":
    main()
