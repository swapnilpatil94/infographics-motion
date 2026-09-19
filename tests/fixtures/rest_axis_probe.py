import json, math, sys
import bpy
out = {}
for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
    cid = arm.name.split("rig_")[1]
    for part, bone in (("upperarm_R", "ARM_R"), ("forearm_R", "FOREARM_R"), ("thigh_R", "THIGH_R"), ("shin_R", "SHIN_R"), ("upperarm_L", "ARM_L"), ("forearm_L", "FOREARM_L")):
        b = arm.data.bones[bone]
        d = arm.matrix_world.to_3x3() @ (b.tail_local - b.head_local)
        ob = bpy.data.objects[f"{part}_{cid}"]
        v = [ob.matrix_world @ x.co for x in ob.data.vertices]
        ax = (v[2] + v[3]) / 2 - (v[0] + v[1]) / 2
        a_bone = math.degrees(math.atan2(d.x, -d.z))
        a_mesh = math.degrees(math.atan2(ax.x, -ax.z))
        out[f"{cid}:{part}"] = round(a_bone - a_mesh, 3)
print("PROBE", json.dumps(out))
