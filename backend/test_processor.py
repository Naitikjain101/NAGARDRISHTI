import sys
import json
from ai.unified.processor import UnifiedVideoProcessor

def main():
    processor = UnifiedVideoProcessor()
    video_path = "/Users/naitikjain/Documents/Nagardristi2.0/backend/uploads/88f3aefd-d6ef-44fe-9564-bcec63ec960e.mp4"
    results_dir = "/Users/naitikjain/Documents/Nagardristi2.0/backend/results/test"
    print("Processing video...")
    result_path = processor.process(video_path, "test_job_id", results_dir)
    print("Parsing results...")
    with open(f"{results_dir}/test_job_id_unified.json") as f:
        result = json.load(f)
    events = result.get("pothole_events", [])
    print(f"Total pothole events: {len(events)}")
    confirmed = [e for e in events if e.get("status") == "confirmed"]
    print(f"Confirmed pothole events: {len(confirmed)}")

if __name__ == "__main__":
    main()
