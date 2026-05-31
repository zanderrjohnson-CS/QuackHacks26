import cv2
import numpy as np
import json
import os

# --- Config ---
CAMERA_INDEX = 0
SHOT_FILE = "/Users/zander/Desktop/hackathon2026/shot.json"
AIM_FILE  = "/Users/zander/Desktop/hackathon2026/aim.json"

# Ball (neon green) - update from calibrate.py
BALL_LOWER = np.array([38, 150, 110])
BALL_UPPER = np.array([52, 210, 200])

# Putter tape (orange/red) - update from calibrate.py
TAPE_LOWER = np.array([0, 151, 164])
TAPE_UPPER = np.array([12, 255, 255])

# Tuning
MIN_DISPLACEMENT = 4      # px in one frame to count as "ball started moving"
SPEED_DIVISOR    = 15.0   # px/frame mapped to 1.0 power; raise to make shots softer
MIN_POINT_SEPARATION = 40 # min px between the two putter dots (rejects unstable angles)

# --- States ---
STATE_START  = "START"    # set the default/straight direction
STATE_AIM    = "AIM"      # tracking putter, arrow follows live
STATE_LOCKED = "LOCKED"   # baseline recorded, waiting for hit
STATE_DONE   = "DONE"     # shot computed and sent

state = STATE_START
default_putter_angle = None  # putter angle defining "straight", set in START
baseline_angle  = None    # putter angle at lock
ball_start_pos  = None    # ball position at lock
tracking        = False   # has the ball started moving?
ball_track      = []      # ball positions once moving
prev_ball_pos   = None


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
    # reject if the two points are too close (noise makes angle unstable)
    d = np.sqrt((points[0][0]-points[1][0])**2 + (points[0][1]-points[1][1])**2)
    if d < MIN_POINT_SEPARATION:
        return None, None, None
    # consistent ordering (leftmost first) to avoid 180 flips
    points = sorted(points, key=lambda p: p[0])
    p1, p2 = points[0], points[1]
    centroid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
    angle = float(np.degrees(np.arctan2(p2[1] - p1[1], p2[0] - p1[0])))
    return centroid, angle, (p1, p2)


def write_aim(offset_deg):
    try:
        with open(AIM_FILE, "w") as f:
            json.dump({"angle": float(offset_deg)}, f)
    except:
        pass


def compute_and_send_shot():
    global ball_track, ball_start_pos, baseline_angle

    # need start position and at least one tracked point
    if ball_start_pos is None or len(ball_track) < 2:
        print("Not enough data to compute shot")
        return False

    # final position = last solid detection (avoid half-cut-off edge frame: use second-to-last if available)
    end_pos = ball_track[-1]
    if len(ball_track) >= 3:
        end_pos = ball_track[-2]

    # travel vector from locked start to end
    dx = end_pos[0] - ball_start_pos[0]
    dy = end_pos[1] - ball_start_pos[1]
    travel_angle = float(np.degrees(np.arctan2(dy, dx)))

    # offset relative to locked baseline
    offset_angle = travel_angle - baseline_angle

    # normalize to -180..180
    while offset_angle > 180:
        offset_angle -= 360
    while offset_angle < -180:
        offset_angle += 360

    # speed = median of first few frame-to-frame displacements (initial launch speed)
    vels = []
    for i in range(min(4, len(ball_track) - 1)):
        a, b = ball_track[i], ball_track[i + 1]
        vels.append(np.sqrt((b[0] - a[0])**2 + (b[1] - a[1])**2))
    speed_px = float(np.median(vels)) if vels else 0.0

    result = {
        "impact_detected": True,
        "ball_speed": float(min(speed_px / SPEED_DIVISOR, 1.0)),
        "ball_angle": float(offset_angle)
    }
    with open(SHOT_FILE, "w") as f:
        json.dump(result, f)

    if os.path.exists(AIM_FILE):
        os.remove(AIM_FILE)

    print(f"SHOT: speed={result['ball_speed']:.2f}  angle={offset_angle:.1f} deg  (travel={travel_angle:.1f}, base={baseline_angle:.1f})")
    return True


# --- Main loop ---
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)
for _ in range(30):
    cap.read()

print("START: aim straight, S to set | AIM: rotate, L to lock | HIT | R = reset | Q = quit")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    ball_pos = find_ball(hsv)
    putter_centroid, putter_angle, putter_points = find_putter(hsv)

    # draw ball
    if ball_pos:
        cv2.circle(display, ball_pos, 10, (0, 255, 0), 2)
        cv2.circle(display, ball_pos, 2, (0, 255, 0), -1)

    # draw putter
    if putter_centroid and putter_points:
        p1, p2 = putter_points
        cv2.circle(display, p1, 8, (0, 165, 255), -1)
        cv2.circle(display, p2, 8, (0, 165, 255), -1)
        cv2.line(display, p1, p2, (0, 165, 255), 2)

    # draw ball trail (path it has tracked since the hit)
    if len(ball_track) >= 2:
        for i in range(1, len(ball_track)):
            cv2.line(display, ball_track[i-1], ball_track[i], (255, 0, 255), 2)
        # mark locked start position
        if ball_start_pos:
            cv2.circle(display, ball_start_pos, 6, (255, 255, 0), 2)

    # mark locked start even before movement
    elif ball_start_pos and state == STATE_LOCKED:
        cv2.circle(display, ball_start_pos, 6, (255, 255, 0), 2)

    # --- START ---
    if state == STATE_START:
        cv2.putText(display, "START - aim putter at straight, press S to set",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    # --- AIM ---
    elif state == STATE_AIM:
        cv2.putText(display, "AIM - rotate putter to aim, press L to lock",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        # arrow follows putter relative to the default straight direction
        if putter_angle is not None and default_putter_angle is not None:
            rel = putter_angle - default_putter_angle
            while rel > 180:  rel -= 360
            while rel < -180: rel += 360
            write_aim(float(rel))

    # --- LOCKED ---
    elif state == STATE_LOCKED:
        cv2.putText(display, "LOCKED - replicate angle and HIT", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        # arrow is frozen in Godot now (we stop writing aim.json).
        # show the user how far their putter is from the locked baseline as a guide.
        if putter_angle is not None and baseline_angle is not None:
            offset = putter_angle - baseline_angle
            while offset > 180:  offset -= 360
            while offset < -180: offset += 360
            color = (0, 255, 0) if abs(offset) < 5 else (0, 165, 255)
            cv2.putText(display, f"Putter offset from lock: {offset:.1f} deg",
                        (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # detect ball starting to move
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
                # ball gone -> off screen -> compute
                if len(ball_track) >= 2:
                    compute_and_send_shot()
                    state = STATE_DONE

        if ball_pos:
            prev_ball_pos = ball_pos

    # --- DONE ---
    elif state == STATE_DONE:
        cv2.putText(display, "SHOT SENT - Press R to reset", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

    cv2.imshow("Putt Tracker", display)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('s') and state == STATE_START:
        if putter_angle is not None:
            default_putter_angle = putter_angle
            write_aim(0.0)  # arrow points straight (default) to begin
            state = STATE_AIM
            print(f"START set: default straight = {default_putter_angle:.1f} deg")
        else:
            print("Can't set start - need putter visible")
    elif key == ord('l') and state == STATE_AIM:
        if putter_angle is not None and ball_pos is not None:
            baseline_angle = putter_angle - 90.0
            ball_start_pos = ball_pos
            prev_ball_pos = ball_pos
            tracking = False
            ball_track = []
            # freeze arrow: stop writing aim.json so Godot holds last angle
            if os.path.exists(AIM_FILE):
                os.remove(AIM_FILE)
            state = STATE_LOCKED
            print(f"LOCKED: baseline={baseline_angle:.1f} deg, start={ball_start_pos}")
        else:
            print("Can't lock - need both ball and putter visible")
    elif key == ord('r'):
        state = STATE_START
        default_putter_angle = None
        baseline_angle = None
        ball_start_pos = None
        prev_ball_pos = None
        tracking = False
        ball_track = []
        if os.path.exists(SHOT_FILE):
            os.remove(SHOT_FILE)
        if os.path.exists(AIM_FILE):
            os.remove(AIM_FILE)
        print("Reset to START")

cap.release()
cv2.destroyAllWindows()