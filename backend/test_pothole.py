from ultralytics import YOLO

model = YOLO("models/pothole/best.pt")

video = "/Users/naitikjain/Documents/Nagar drishti mp4/potholes.mp4"

results = model.predict(
    source=video,
    conf=0.40,
    stream=True,
    verbose=False
)

total = 0
frames = 0
frames_with_detections = 0
per_frame = []

for i, result in enumerate(results):
    frames += 1
    count = len(result.boxes)
    total += count

    if count > 0:
        frames_with_detections += 1
        per_frame.append((i, count))

print("FRAMES:", frames)
print("TOTAL DETECTIONS:", total)
print("FRAMES WITH DETECTIONS:", frames_with_detections)
print("FIRST 30:", per_frame[:30])
