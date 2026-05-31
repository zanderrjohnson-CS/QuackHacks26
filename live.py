import cv2
import numpy as np
import json
import os

# --- Config ---
CAMERA_INDEX = 0
SHOT_FILE    = "/Users/zander/Desktop/hackathon2026/shot.json"
COMMAND_FILE = "/Users/zander/Desktop/hackathon2026/command.json"
STATUS_FILE  = "/Users/zander/Desktop/hackathon2026/status.json"  # Python -> Godot

# Ball (neon green)
BALL_LOWER = np.array([27, 102, 186])
BALL_UPPER = np.array([61, 255, 255])

# Putter tape (orange/red)
TAPE_LOWER = np.array([0, 84, 207])
TAPE_UPPER = np.array([19, 229, 255])

# Tuning
MIN_DISPLACEMENT     = 4
SPEED_DIVISOR        = 6.0
MIN_POINT_SEPARATION = 40

phase = "START"

baseline_angle = None
ball_start_pos = None
tracking       = False
ball_track     = []
prev_ball_pos  = None
lock_pending   = False


def find_ball(hsv):
    mask = cv2.inRange(hsv, BALL_LOWER, BALL_UPPER)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 50:
        return None
    M = cv2.moments(c)
    if M["m00"] == 0:
        return None
    return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))


def find_putter(hsv):
    mask = cv2.inRange(hsv, TAPE_LOWER, TAPE_UPPER)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) > 100]
    if len(contours) < 2:
        return None, None, None
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:2]
    points = []
    for c in contours:
        M = cv2.moments(c)
        if M["m00"] > 0:
            points.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))
    if len(points) < 2:
        return None, None, None
    d = np.sqrt((points[0][0]-points[1][0])**2 + (points[0][1]-points[1][1])**2)
    if d < MIN_POINT_SEPARATION:
        return None, None, None
    points = sorted(points, key=lambda p: p[0])
    p1, p2 = points[0], points[1]
    centroid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
    angle = float(np.degrees(np.arctan2(p2[1] - p1[1], p2[0] - p1[0])))
    return centroid, angle, (p1, p2)


def read_command():
    if not os.path.exists(COMMAND_FILE):
        return None
    try:
        with open(COMMAND_FILE) as f:
            data = json.load(f)
        return data.get("phase")
    except:
        return None


def write_status(status):
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump({"status": status}, f)
    except:
        pass


def compute_and_send_shot():
    global ball_track, ball_start_pos, baseline_angle
    if ball_start_pos is None or len(ball_track) < 2:
        print("Not enough data to compute shot")
        return False
    end_pos = ball_track[-1]
    if len(ball_track) >= 3:
        end_pos = ball_track[-2]
    dx = end_pos[0] - ball_start_pos[0]
    dy = end_pos[1] - ball_start_pos[1]
    travel_angle = float(np.degrees(np.arctan2(dy, dx)))
    offset_angle = travel_angle - baseline_angle
    while offset_angle > 180:  offset_angle -= 360
    while offset_angle < -180: offset_angle += 360

    vels = []
    for i in range(min(4, len(ball_track) - 1)):
        a, b = ball_track[i], ball_track[i + 1]
        vels.append(np.sqrt((b[0]-a[0])**2 + (b[1]-a[1])**2))
    speed_px = float(np.median(vels)) if vels else 0.0

    result = {
        "impact_detected": True,
        "ball_speed": float(max(0.4, min(speed_px / SPEED_DIVISOR, 1.0))),
        "ball_angle": float(offset_angle)
    }
    with open(SHOT_FILE, "w") as f:
        json.dump(result, f)
    print(f"SHOT: speed_px={speed_px:.2f} angle_offset={offset_angle:.1f} deg")
    return True


# --- Main loop ---
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)
for _ in range(30):
    cap.read()

print("Controlled from Godot window: arrow keys aim | S show putter | L lock+hit | R reset")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    ball_pos = find_ball(hsv)
    putter_centroid, putter_angle, putter_points = find_putter(hsv)

    cmd = read_command()
    if cmd and cmd != phase:
        if cmd == "LOCKED":
            lock_pending = True
        if cmd == "START":
            baseline_angle = None
            ball_start_pos = None
            prev_ball_pos = None
            tracking = False
            ball_track = []
            if os.path.exists(SHOT_FILE):
                os.remove(SHOT_FILE)
            write_status("OK")
        phase = cmd

    if ball_pos:
        cv2.circle(display, ball_pos, 10, (0, 255, 0), 2)
        cv2.circle(display, ball_pos, 2, (0, 255, 0), -1)

    if phase in ("PUTTER", "LOCKED") and putter_centroid and putter_points:
        p1, p2 = putter_points
        cv2.circle(display, p1, 8, (0, 165, 255), -1)
        cv2.circle(display, p2, 8, (0, 165, 255), -1)
        cv2.line(display, p1, p2, (0, 165, 255), 2)

    if len(ball_track) >= 2:
        for i in range(1, len(ball_track)):
            cv2.line(display, ball_track[i-1], ball_track[i], (255, 0, 255), 2)
        if ball_start_pos:
            cv2.circle(display, ball_start_pos, 6, (255, 255, 0), 2)
    elif ball_start_pos and phase == "LOCKED":
        cv2.circle(display, ball_start_pos, 6, (255, 255, 0), 2)

    # --- phase behavior ---
    if phase == "START":
        cv2.putText(display, "START - aim with arrow keys in Godot, S when ready",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

    elif phase == "PUTTER":
        cv2.putText(display, "PUTTER - line up putter, L to lock",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    elif phase == "LOCKED":
        # capture baseline EXACTLY once on entry; reject if putter not visible
        if lock_pending:
            lock_pending = False
            if putter_angle is not None and ball_pos is not None:
                baseline_angle = putter_angle - 90.0
                ball_start_pos = ball_pos
                prev_ball_pos = ball_pos
                tracking = False
                ball_track = []
                write_status("LOCK_OK")
                print(f"Baseline captured: {baseline_angle:.1f} deg")
            else:
                # reject the lock: tell Godot to go back to PUTTER, user must press L again
                write_status("LOCK_FAILED")
                phase = "PUTTER"
                print("LOCK REJECTED - putter not visible. Press L again.")

        if phase == "LOCKED":
            cv2.putText(display, "LOCKED - HIT the ball", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            if baseline_angle is not None:
                if not tracking and ball_pos and prev_ball_pos:
                    dx = ball_pos[0] - prev_ball_pos[0]
                    dy = ball_pos[1] - prev_ball_pos[1]
                    if np.sqrt(dx**2 + dy**2) >= MIN_DISPLACEMENT:
                        tracking = True
                        ball_track = [prev_ball_pos, ball_pos]
                elif tracking:
                    if ball_pos:
                        ball_track.append(ball_pos)
                    else:
                        if len(ball_track) >= 2:
                            compute_and_send_shot()
                            phase = "DONE"
                if ball_pos:
                    prev_ball_pos = ball_pos
        else:
            cv2.putText(display, "LOCK FAILED - press L again", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    elif phase == "DONE":
        cv2.putText(display, "SHOT SENT - R to reset (in Godot)", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

    cv2.imshow("Putt Tracker", display)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()