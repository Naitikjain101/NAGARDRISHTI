from ultralytics import YOLO
import os
from pathlib import Path

def train_waterlogging_model():
    dataset_yaml = Path("backend/data/waterlogging/yolo_dataset/data.yaml")
    
    if not dataset_yaml.exists():
        print(f"Error: {dataset_yaml} not found. Please run export first.")
        return
        
    print("Initializing YOLOv8n-seg model...")
    # Load a pretrained segmentation model
    model = YOLO("yolov8n-seg.pt")
    
    print("Starting training on waterlogging dataset...")
    # Train the model
    # We use a small number of epochs and image size suitable for a quick local test
    # (In production, you would scale these up)
    results = model.train(
        data=str(dataset_yaml.absolute()),
        epochs=15,  # Keep it small for speed since this is a demonstration
        imgsz=640,
        batch=4,
        project="models/waterlogging",
        name="v1",
        device="cpu", # Use cpu for guaranteed compat on unknown mac chip
        workers=0
    )
    
    print("Training complete!")
    print(f"Best weights saved to models/waterlogging/v1/weights/best.pt")

if __name__ == "__main__":
    train_waterlogging_model()
