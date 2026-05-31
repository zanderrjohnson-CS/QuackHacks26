extends RigidBody3D

var shot_file = "/Users/zander/Desktop/hackathon2026/shot.json"
var aim_file  = "/Users/zander/Desktop/hackathon2026/aim.json"

var should_reset   = false
var start_position = Vector3.ZERO
var has_shot       = false
var arrow_angle    = 0.0      # current arrow angle (degrees)

var arrow_pivot: Node3D       # child of ball, holds the arrow
var arrow_mesh: MeshInstance3D

@export var default_angle: float  = 0.0
@export var arrow_distance: float = 0.45
@export var power_scale: float    = 20.0
@export var rolling_friction: float = 4.0  # constant deceleration force


var has_moved = false   # becomes true once ball is actually rolling


func _physics_process(delta):
	if has_shot and not freeze:
		var vel = linear_velocity
		var speed = vel.length()

		# wait until the ball is actually moving before allowing stop detection
		if speed > 0.5:
			has_moved = true

		if speed > 0.01:
			var decel = rolling_friction * delta
			if decel >= speed:
				linear_velocity = Vector3.ZERO
				angular_velocity = Vector3.ZERO
				if has_moved:
					_on_ball_stopped()
			else:
				apply_central_force(-vel.normalized() * rolling_friction)
		elif has_moved:
			_on_ball_stopped()


func _on_ball_stopped():
	# ball has come to rest after a shot: re-arm from this new position
	has_shot = false
	has_moved = false
	start_position = global_position   # new resting spot becomes the reset point
	# flatten any roll tilt so the parented arrow sits flat
	global_rotation = Vector3.ZERO
	arrow_angle = default_angle
	arrow_pivot.visible = true
	_update_arrow_visual()
	# freeze so it stays still and flat while aiming the next shot
	freeze = true


func _ready():
	start_position = global_position
	arrow_angle = default_angle
	freeze_mode = RigidBody3D.FREEZE_MODE_KINEMATIC
	freeze = true   # stay still and flat until shot fired
	_create_arrow()


func _create_arrow():
	# pivot is a child of the ball, sits at ball center
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

	# cone flat along pivot +X
	arrow_mesh.rotation = Vector3(0.0, 0.0, deg_to_rad(-90.0))
	arrow_mesh.position = Vector3(arrow_distance, 0.0, 0.0)


func _update_arrow_visual():
	# pivot only rotates on Y; because we freeze ball rotation, this stays flat
	arrow_pivot.rotation = Vector3(0.0, deg_to_rad(-arrow_angle), 0.0)


func _process(_delta):
	if has_shot:
		return

	# AIM phase: arrow follows putter live
	# LOCKED phase: arrow frozen (Python stops writing aim.json after lock,
	#               or writes the offset — handled by aim.json contents)
	if arrow_pivot.visible and FileAccess.file_exists(aim_file):
		var file = FileAccess.open(aim_file, FileAccess.READ)
		var data = JSON.parse_string(file.get_as_text())
		file.close()
		if data and data.has("angle"):
			arrow_angle = default_angle + data["angle"]
			_update_arrow_visual()

	# poll for shot
	if FileAccess.file_exists(shot_file):
		var file = FileAccess.open(shot_file, FileAccess.READ)
		var data = JSON.parse_string(file.get_as_text())
		file.close()
		if data and data.get("impact_detected", false):
			apply_shot(data["ball_speed"], data["ball_angle"])
			has_shot = true
			DirAccess.remove_absolute(shot_file)


func apply_shot(speed: float, offset_degrees: float):
	# ball travels at arrow direction + the off-straight offset
	var total_angle = arrow_angle + offset_degrees
	var rad = deg_to_rad(total_angle)
	var direction = Vector3(cos(rad), 0.0, sin(rad))
	print("SHOT applied: speed=", speed, " power=", speed * power_scale, " dir=", direction)
	# unfreeze so it can roll
	freeze = false
	# apply impulse next physics frame to ensure unfreeze has taken effect
	call_deferred("_launch", direction * speed * power_scale)
	arrow_pivot.visible = false
func _launch(impulse: Vector3):
	linear_velocity = Vector3.ZERO
	angular_velocity = Vector3.ZERO
	apply_central_impulse(impulse)
	print("Launched, velocity now: ", linear_velocity)


func reset_ball():
	print("RESET")
	has_shot = false
	arrow_angle = default_angle
	arrow_pivot.visible = true
	_update_arrow_visual()
	should_reset = true


func _integrate_forces(state):
	if should_reset:
		var t = Transform3D(Basis(), start_position)  # identity basis = flat
		state.transform = t
		state.linear_velocity  = Vector3.ZERO
		state.angular_velocity = Vector3.ZERO
		should_reset = false
		# re-freeze so ball stays still and flat while aiming next shot
		freeze = true


func _input(event):
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_SPACE:
			apply_shot(0.7, 0.0)
		elif event.keycode == KEY_R:
			reset_ball()
