import cv2
import sys
video_id = "e54d43f9-74da-4036-94af-102e90c3956a"
path = f"backend/uploads/{video_id}.mp4"
cap = cv2.VideoCapture(path)
print("Opened:", cap.isOpened())
cap.set(cv2.CAP_PROP_POS_MSEC, 25.52 * 1000)
ret, frame = cap.read()
print("Read:", ret)
if ret:
    print("Frame max val:", frame.max(), "mean:", frame.mean())
cap.release()
