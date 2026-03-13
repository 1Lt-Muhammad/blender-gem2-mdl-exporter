bl_info = {
    "name": "GEM2 Engine MDL",
    "author": "1Lt. Muhammad",
    "version": (0, 7, 2),
    "blender": (4, 3, 0),
    "location": "File > Import-Export",
    "description": "GEM2 Engine O MDL Files",
    "warning": "",
    "doc_url": "https://github.com/1Lt-Muhammad/blender-gem2-mdl-exporter",
    "support": 'OFFICIAL',
    "category": "Import-Export",
}

if "bpy" in locals():
    import importlib
    if "mdl_export" in locals():
        importlib.reload(mdl_export)

import bpy
from bpy.app.translations import pgettext_tip as tip_
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
)
from bpy_extras.io_utils import (
    ExportHelper,
    poll_file_object_drop,
    orientation_helper,
    axis_conversion,
)

@orientation_helper(axis_forward='X', axis_up='Z')
class ExportGEM2MDL(bpy.types.Operator, ExportHelper):
    """Export a GEM2 Engine MDL file"""
    bl_idname = "export_scene.gem2mdl"
    bl_label = "Export MDL"
    bl_options = {'UNDO'}

    directory: StringProperty(
        subtype='DIR_PATH',
        options={'HIDDEN'},
    )

    filename_ext = ""

    apply_unit_scale: BoolProperty(
        name="Apply Unit Scale",
        description="Take into account current Blender units settings (1m in blender = 1m in game, if unset, raw Blender Units values are used as-is)",
        default=True,
    )
    use_mirror: BoolProperty(
        name="Mirror Model",
        description="Mirror the model Y axis, export mirrored meshes",
        default=False,
    )


    def execute(self, context):
        global_matrix = axis_conversion(
                                         from_forward=self.axis_forward,
                                         from_up=self.axis_up,
                                         to_forward='X',
                                         to_up='Z',
                                         ).to_4x4()
        global_matrix = global_matrix.Scale(self.use_mirror*2-1, 4, (0, 1, 0)) @ global_matrix

        keywords = self.as_keywords(ignore=("filter_glob", "directory", "ui_tab", "filepath", "files", "check_existing", "axis_forward", "axis_up", "use_mirror"))

        keywords["global_matrix"] = global_matrix

        from . import mdl_export

        if self.directory:
            return mdl_export.export(self.directory, self, **keywords)


class IO_FH_gem2mdl(bpy.types.FileHandler):
    bl_idname = "IO_FH_gem2mdl"
    bl_label = "MDL"
    bl_export_operator = "export_scene.gem2mdl"
    bl_file_extensions = ".mdl"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


def menu_func_export(self, context):
    self.layout.operator(ExportGEM2MDL.bl_idname, text="GEM2 Engine (.mdl)")


classes = (
    ExportGEM2MDL,
    IO_FH_gem2mdl,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
