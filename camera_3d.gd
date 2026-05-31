extends Camera3D

@export var target: NodePath
@export var offset = Vector3(-4.0, 2.1, 0.4)   # camera pos minus ball start pos
@export var smooth_speed = 5.0

var target_node: Node3D

func _ready():
	target_node = get_node(target)

func _process(delta):
	if target_node:
		var target_pos = target_node.global_position + offset
		global_position = global_position.lerp(target_pos, smooth_speed * delta)
		look_at(target_node.global_position, Vector3.UP)
