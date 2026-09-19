import bpy, sys, traceback, json, importlib
res = {}
def attempt(name, path, pkg, fn):
    sys.path.insert(0, path)
    try:
        m = importlib.import_module(pkg)
        m.register()
        res[name] = {"register": "ok"}
        try:
            res[name]["probe"] = fn(m)
        except Exception as e:
            res[name]["probe"] = "FAILED: %s: %s" % (type(e).__name__, str(e)[:200])
    except Exception as e:
        res[name] = {"register": "FAILED: %s: %s" % (type(e).__name__, str(e)[:260])}
    sys.path.pop(0)

def tiny(m):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.tiny2drig.create_2d_armature()
    ob = bpy.context.object
    return {"armature": ob.name, "bones": [b.name for b in ob.data.bones]}
def puppet(m):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.puppet.create_puppet()
    ob = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    return {"armature": ob.name, "n_bones": len(ob.data.bones), "sample": [b.name for b in ob.data.bones][:14],
            "gp_layers": [len(o.data.layers) for o in bpy.data.objects if o.type == 'GREASEPENCIL']}
def coa(m):
    import coa_tools2
    return {"version": getattr(coa_tools2, "bl_info", {}).get("version"), "note": "registered"}
attempt("tiny_2d_rig_tools", "/tmp/rigresearch/Tiny-2D-Rig-Tools", "tiny_2d_rig_tools", tiny)
attempt("puppet_mode", "/tmp/rigresearch/puppet-mode", "puppet_mode", puppet)
attempt("coa_tools2", "/tmp/rigresearch/coa_tools2", "coa_tools2", coa)
print("PROBE", json.dumps(res, default=str))
