This addon will allow you to export GEM2 game engine PLY and VOL files. It also creates a Scene.txt file to help you write the MDL file.

To export VOL files you need to add 'volume' as a custom property to mesh data (not object).

The addon respects the units used by both GEM2 game engine and Blender, as long as 'Apply Unit Scale' is checked, 1 meter in Blender = 1 meter in GEM game engine.
If the models got too big and you can't make sense of the scaling system, just unckeck 'Apply Unit Scale' from the export pop up options.

If the model was flipped after exporting, try checking 'Mirror' in export settings.

There is an example Blender file for humanskins in samples folder.
