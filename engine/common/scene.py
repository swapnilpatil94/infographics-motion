"""Scene bootstrap helpers shared by build/test entrypoints."""
import bpy


def clear_scene():
    """Removes every object and empty collection, including Blender's
    factory-default Cube/Camera/Light which live in a nested 'Collection'
    that scene.collection.objects does NOT reach."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        if coll.users == 0:
            bpy.data.collections.remove(coll)
