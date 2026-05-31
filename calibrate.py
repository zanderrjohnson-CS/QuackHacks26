import cv2
import numpy as np

CAMERA_INDEX = 0

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)
for _ in range(60):
    cap.read()

print("Position ball and putter in frame, then press ENTER")
input()

ret, frame = cap.read()
cap.release()

if not ret:
    print("Failed to capture frame")
    exit()

cv2.imwrite("calibration_frame.png", frame)
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

ball_clicks = []
putter_clicks = []
mode = "ball"   # start with ball

def click(event, x, y, flags, param):
    global mode
    if event == cv2.EVENT_LBUTTONDOWN:
        val = hsv[y, x]
        if mode == "ball":
            ball_clicks.append(val)
            print(f"[BALL]   ({x},{y}): H={val[0]} S={val[1]} V={val[2]}")
        else:
            putter_clicks.append(val)
            print(f"[PUTTER] ({x},{y}): H={val[0]} S={val[1]} V={val[2]}")

def report(name, clicks):
    if not clicks:
        print(f"\n{name}: no clicks")
        return
    vals = np.array(clicks)
    h_lo, h_hi = vals[:,0].min(), vals[:,0].max()
    s_lo, s_hi = vals[:,1].min(), vals[:,1].max()
    v_lo, v_hi = vals[:,2].min(), vals[:,2].max()
    print(f"\n--- {name} ---")
    print(f"H: {h_lo}-{h_hi}   S: {s_lo}-{s_hi}   V: {v_lo}-{v_hi}")
    lower = [max(0, h_lo-10), max(0, s_lo-40), max(0, v_lo-40)]
    upper = [min(180, h_hi+10), min(255, s_hi+40), min(255, v_hi+40)]
    print(f"LOWER = np.array([{lower[0]}, {lower[1]}, {lower[2]}])")
    print(f"UPPER = np.array([{upper[0]}, {upper[1]}, {upper[2]}])")

print("\nClick spots on the GREEN BALL.")
print("Press P to switch to PUTTER, R to reset clicks, Q when done.\n")

cv2.imshow("Calibrate - BALL mode (P=putter, R=reset, Q=quit)", frame)
cv2.setMouseCallback("Calibrate - BALL mode (P=putter, R=reset, Q=quit)", click)

while True:
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('p'):
        mode = "putter"
        print("\n>>> Switched to PUTTER mode. Click the tape spots.\n")
    elif key == ord('b'):
        mode = "ball"
        print("\n>>> Switched to BALL mode.\n")
    elif key == ord('r'):
        ball_clicks.clear()
        putter_clicks.clear()
        print("\n>>> Clicks reset.\n")

cv2.destroyAllWindows()

report("BALL", ball_clicks)
report("PUTTER", putter_clicks)