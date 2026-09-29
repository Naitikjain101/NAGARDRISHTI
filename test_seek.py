import cv2
import sys

video_id = "e54d43f9-74da-4036-94af-102e90c3956a"
path = f"backend/uploads/{video_id}.mp4"

def get_msec(t):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ret, frame = cap.read()
    cap.release()
    return frame.mean() if ret else None

print("25.52:", get_msec(25.52))
print("26.84:", get_msec(26.84))
print("20.84:", get_msec(20.84))

