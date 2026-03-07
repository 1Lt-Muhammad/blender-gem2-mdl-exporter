This addon will allow you to export GEM2 game engine PLY, VOL, and MTL files. It also creates a simple MDL file (obstacles, areas, and animations aren't supported yet).

The addon detect meshes and volumes automatically. Meshes can be used for both PLY and VOL.

To export VOL files, just make sure the object name ends in '.vol'. To export primitive VOL files, you need to add 'volume' as a custom property to the mesh data (not object). The volume value can be an integer (1, 2, or 3) or a string (sphere, cylinder, or box).

The addon now export simple MTL files for the materials with the textures having the same name as the material. Creates a simple txt file with textures names to ease modifying MTL files.

The addon respects the units used by both GEM2 game engine and Blender, as long as 'Apply Unit Scale' is checked, 1 meter in Blender = 1 meter in GEM game engine.
If the models got too big and you can't make sense of the scaling system, just uncheck 'Apply Unit Scale' from the export pop up options.

If the model was flipped after exporting, try unchecking 'Mirror' in export settings.

There is an example Blender file for humanskins in samples folder.
