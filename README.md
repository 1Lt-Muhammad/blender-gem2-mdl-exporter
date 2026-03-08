This addon will allow you to export GEM2 game engine MDL, PLY, VOL, and MTL files (obstacles, areas, and animations aren't supported yet).

The addon detects meshes and volumes automatically. Meshes can be used for both PLY and VOL exports.

To export VOL files, just make sure the object name ends in '.vol'. To export primitive VOL files, you need to add 'volume' as a custom property to the mesh data (not object). The volume value can be an integer (1, 2, or 3) or a string (sphere, cylinder, or box).

The addon now export MTL files. However, you need to copy your textures manually to the folder. You may need to modify MTL files.

The addon respects the units used by both GEM2 game engine and Blender, as long as 'Apply Unit Scale' is checked, 1 meter in Blender = 1 meter in GEM game engine.
If the models got too big and you can't make sense of the scaling system, just uncheck 'Apply Unit Scale' from the export pop up options.

If the model was flipped after exporting, try unchecking 'Mirror Model' in export settings.

There is an example Blender file for humanskins in samples folder.
