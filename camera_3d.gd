extends Camera3D

@export var target: NodePath
@export var offset = Vector3(-4.0, 2.1, 0.4)   # follow offset (camera pos minus ball pos)
@export var smooth_speed = 5.0

# orbit/pan controls
@export var orbit_speed = 0.01
@export var pan_speed   = 0.01
@export var zoom_speed  = 0.5

var target_node: RigidBody3D

# manual camera state (spherical coords around a focus point)
var manual_control = false
var focus_point = Vector3.ZERO
var cam_distance = 5.0
var yaw   = 0.0
var pitch = -0.6

var middle_held = false
var shift_held  = false


func _ready():
	target_node = get_node(target)
	# initialize orbit params from the starting offset
	cam_distance = offset.length()
	focus_point = target_node.global_position if target_node else Vector3.ZERO


func _unhandled_input(event):
	# only allow manual camera while the ball is at rest (frozen = aiming phase)
	if not _is_aiming():
		return

	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_MIDDLE:
			middle_held = event.pressed
			manual_control = true
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			cam_distance = max(1.0, cam_distance - zoom_speed)
			manual_control = true
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			cam_distance += zoom_speed
			manual_control = true

	elif event is InputEventKey:
		if event.keycode == KEY_SHIFT:
			shift_held = event.pressed

	elif event is InputEventMouseMotion and middle_held:
		manual_control = true
		if shift_held:
			# pan: move focus point in camera's local right/up plane
			var right = global_transform.basis.x
			var up = global_transform.basis.y
			focus_point -= right * event.relative.x * pan_speed
			focus_point += up * event.relative.y * pan_speed
		else:
			# orbit: adjust yaw/pitch
			yaw   -= event.relative.x * orbit_speed
			pitch -= event.relative.y * orbit_speed
			pitch = clamp(pitch, -1.5, -0.05)  # keep above ground, below top


func _is_aiming() -> bool:
	# ball frozen = at rest = aiming phase
	return target_node != null and target_node.freeze


func _process(delta):
	if not target_node:
		return

	if _is_aiming() and manual_control:
		# manual orbit camera around focus point
		var off = Vector3(
			cos(pitch) * cos(yaw),
			sin(-pitch),
			cos(pitch) * sin(yaw)
		) * cam_distance
		global_position = focus_point + off
		look_at(focus_point, Vector3.UP)
	elif _is_aiming():
		# at rest but not manually controlling: gentle follow to keep ball framed
		var target_pos = target_node.global_position + offset
		global_position = global_position.lerp(target_pos, smooth_speed * delta)
		look_at(target_node.global_position, Vector3.UP)
		focus_point = target_node.global_position
	else:
		# ball is moving: keep camera position, only rotate to face the ball
		manual_control = false
		look_at(target_node.global_position, Vector3.UP)
		focus_point = target_node.global_position
