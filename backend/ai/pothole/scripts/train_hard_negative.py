import os
import shutil
from pathlib import Path
from ultralytics import YOLO

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
DATA_YAML = BASE_DIR / "datasets" / "pothole_hard_negative" / "data.yaml"
WEIGHTS_DIR = BASE_DIR / "backend" / "ai" / "pothole" / "weights"
BASE_MODEL = WEIGHTS_DIR / "pothole_yolov8_peterhdd.pt"
OUTPUT_MODEL = WEIGHTS_DIR / "pothole_yolov8m_hardnegative_v1.pt"

print(f"Starting experimental fine-tuning offline.")
print(f"Base model: {BASE_MODEL}")
print(f"Data config: {DATA_YAML}")

# Load the pretrained model
model = YOLO(BASE_MODEL)

# Train the model (short pilot run, 5 epochs, conservative learning rate)
# Augmentations: fliplr (0.5), degrees (0.0), hsv (moderate), scale (0.5)
# Because this is a short run for demonstration, we keep epochs low.
results = model.train(
    data=str(DATA_YAML),
    epochs=5,
    imgsz=640,
    batch=4,
    lr0=0.0001, # Conservative LR for fine-tuning
    device="mps", # Assuming we are on Apple Silicon
    fliplr=0.5,
    scale=0.2,
    perspective=0.0001,
    project=str(BASE_DIR / "runs" / "detect"),
    name="pothole_hardneg_finetune",
    exist_ok=True
)

# Extract best weights and copy to output path
best_weights = Path(model.trainer.best)
print(f"Training completed. Best weights saved to: {best_weights}")

shutil.copy(best_weights, OUTPUT_MODEL)
print(f"Exported experimental weights to: {OUTPUT_MODEL}")
