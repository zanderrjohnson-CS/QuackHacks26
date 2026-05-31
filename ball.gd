extends RigidBody3D

var shot_file    = "/Users/zander/Desktop/hackathon2026/shot.json"
var command_file = "/Users/zander/Desktop/hackathon2026/command.json"
var status_file  = "/Users/zander/Desktop/hackathon2026/status.json"

var should_reset   = false
var start_position = Vector3.ZERO
var has_shot       = false
var has_moved      = false
var arrow_angle    = 0.0      # current arrow angle (degrees)
var slow_frames    = 0        # consecutive frames below stop threshold

# phase: "START" (arrow-key aim) -> "PUTTER" (after S) -> "LOCKED" (after L) -> "DONE"
var phase = "START"

var arrow_pivot: Node3D
var arrow_mesh: MeshInstance3D

@export var default_angle: float    = 0.0
@export var arrow_distance: float   = 0.45
@export var power_scale: float      = 20.0
@export var rolling_friction: float = 2.0
@export var arrow_key_step: float   = 5.0   # degrees per arrow-key press
@export var stop_speed: float       = 0.3   # below this speed = "slow"
@export var stop_frames_needed: int = 30    # must be slow this many frames to stop


func _ready():
	start_position = global_position
	arrow_angle = default_angle
	freeze_mode = RigidBody3D.FREEZE_MODE_KINEMATIC
	freeze = true
	_create_arrow()
	_write_command("START")


func _create_arrow():
	arrow_pivot = Node3D.new()
	add_child(arrow_pivot)

	arrow_mesh = MeshInstance3D.new()
	var mesh = CylinderMesh.new()
	mesh.top_radius    = 0.0
	mesh.bottom_radius = 0.08
	mesh.height        = 0.7
	arrow_mesh.mesh = mesh

	var mat = StandardMaterial3D.new()
	mat.albedo_color = Color(1.0, 0.5, 0.0)
	mat.emission_enabled = true
	mat.emission = Color(1.0, 0.4, 0.0)
	mat.emission_energy_multiplier = 2.0
	arrow_mesh.material_override = mat

	arrow_pivot.add_child(arrow_mesh)
	arrow_mesh.rotation = Vector3(0.0, 0.0, deg_to_rad(-90.0))
	arrow_mesh.position = Vector3(arrow_distance, 0.0, 0.0)


func _update_arrow_visual():
	arrow_pivot.rotation = Vector3(0.0, deg_to_rad(-arrow_angle), 0.0)


func _write_command(cmd: String):
	var f = FileAccess.open(command_file, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify({"phase": cmd}))
		f.close()


func _physics_process(delta):
	if has_shot and not freeze:
		var vel = linear_velocity
		var speed = vel.length()

		if speed > 0.5:
			has_moved = true

		# apply constant rolling friction opposing horizontal motion
		var horiz = Vector3(vel.x, 0.0, vel.z)
		var horiz_speed = horiz.length()
		if horiz_speed > 0.01:
			var decel = rolling_friction * delta
			if decel < horiz_speed:
				apply_central_force(-horiz.normalized() * rolling_friction)

		# stop detection: require sustained low speed, not a single slow frame.
		# this prevents freezing mid-slope when the ball briefly slows.
		if has_moved and speed < stop_speed:
			slow_frames += 1
		else:
			slow_frames = 0

		if slow_frames >= stop_frames_needed:
			linear_velocity = Vector3.ZERO
			angular_velocity = Vector3.ZERO
			_on_ball_stopped()


func _on_ball_stopped():
	has_shot = false
	has_moved = false
	slow_frames = 0
	start_position = global_position
	global_rotation = Vector3.ZERO
	arrow_angle = default_angle
	arrow_pivot.visible = true
	_update_arrow_visual()
	freeze = true
	phase = "START"
	_write_command("START")


func _process(_delta):
	if has_shot:
		return

	# while waiting in LOCKED, check if Python rejected the lock
	if phase == "LOCKED" and FileAccess.file_exists(status_file):
		var sf = FileAccess.open(status_file, FileAccess.READ)
		var sdata = JSON.parse_string(sf.get_as_text())
		sf.close()
		if sdata and sdata.get("status", "") == "LOCK_FAILED":
			phase = "PUTTER"
			print("Lock failed - putter not visible. Press L again.")
			DirAccess.remove_absolute(status_file)

	if phase != "LOCKED":
		if FileAccess.file_exists(shot_file):
			DirAccess.remove_absolute(shot_file)
		return

	if FileAccess.file_exists(shot_file):
		var file = FileAccess.open(shot_file, FileAccess.READ)
		var data = JSON.parse_string(file.get_as_text())
		file.close()
		if data and data.get("impact_detected", false):
			apply_shot(data["ball_speed"], data["ball_angle"])
			has_shot = true
			phase = "DONE"
			DirAccess.remove_absolute(shot_file)


func apply_shot(speed: float, offset_degrees: float):
	var total_angle = arrow_angle + offset_degrees
	var rad = deg_to_rad(total_angle)
	var direction = Vector3(cos(rad), 0.0, sin(rad))
	freeze = false
	slow_frames = 0
	call_deferred("_launch", direction * speed * power_scale)
	arrow_pivot.visible = false


func _launch(impulse: Vector3):
	linear_velocity = Vector3.ZERO
	angular_velocity = Vector3.ZERO
	var min_power = rolling_friction * 2.0
	if impulse.length() < min_power:
		impulse = impulse.normalized() * min_power
	apply_central_impulse(impulse)


func reset_ball():
	has_shot = false
	has_moved = false
	slow_frames = 0
	arrow_angle = default_angle
	arrow_pivot.visible = true
	_update_arrow_visual()
	should_reset = true
	phase = "START"
	_write_command("START")


func _integrate_forces(state):
	if should_reset:
		var t = Transform3D(Basis(), start_position)
		state.transform = t
		state.linear_velocity  = Vector3.ZERO
		state.angular_velocity = Vector3.ZERO
		should_reset = false
		freeze = true


func _input(event):
	if not (event is InputEventKey and event.pressed):
		return

	# START phase: arrow keys rotate the arrow
	if phase == "START":
		if event.keycode == KEY_LEFT:
			arrow_angle -= arrow_key_step
			_update_arrow_visual()
		elif event.keycode == KEY_RIGHT:
			arrow_angle += arrow_key_step
			_update_arrow_visual()
		elif event.keycode == KEY_S:
			phase = "PUTTER"
			_write_command("PUTTER")
			print("Arrow locked at ", arrow_angle, " deg. Line up putter, press L.")

	elif phase == "PUTTER":
		if event.keycode == KEY_L:
			phase = "LOCKED"
			_write_command("LOCKED")
			print("Lock requested. Hit the ball (Python confirms putter visibility).")

	# R resets from any phase
	if event.keycode == KEY_R:
		reset_ball()
