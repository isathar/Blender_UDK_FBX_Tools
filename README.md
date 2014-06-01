Blender -> UDK FBX Tools
=====================

Blender addon that adds editors for smoothing groups, custom vertex normals, and a UDK-optimized exporter that supports both.

The exporter can also calculate tangents and binormals on export, allowing you to take advantage of the xNormal - UDK synced workflow using Blender.

--------------------------------------------------------------------------

This readme is a work in progress, full documentation will be up soon.

--------------------------------------------------------------------------

*Note: The normals and smoothing groups will not affect your displayed mesh in Blender, only in the exported file


*Performance Note: I've tested this on meshes with between 6 and 15000 polys. On my mid-range system (Intel i5-2500 with 8GB of RAM and a Geforce 560ti),
real-time display of normals and my custom angle-based generation algorithm are very slow on anything past 8000 or so polys, depending on the mesh's
density. Checking "Selected Only" in the display section of each tool helps, but will slow things down more as you approach higher counts. I have a 
pretty good idea of why it's doing this and will try to optimize things some more soon.

---------------------------------------------------------------------------

Features:
---------

Editor for Vertex Normals:
--------------------------

	- Manual editing per poly or vertex
	- Automatic generation with several presets for different scenarios
		-- presets: 
			--- Smooth (Blender default)
			--- Angle-Based (slow but customizable algorithm)
			--- Up-Vector
			--- Bent (facing away from 3d cursor)
			--- Ground Foliage (selected ground based vertices point up, everything else bent from cursor)
			--- (TBD: Edge-Based and Smoothing Group-Based)
	- Allows calculating normals for selected faces or the whole mesh
	- Normals can be displayed as lines for visual editing
	- copy/paste selected normals between meshes with identical vert locations (buggy/wip, but fixes modular mesh seams when it works)
	- Real-time in Edit Mode


Editor for Smoothing Groups:
----------------------------

	- Manual editing of smoothing groups per face
	- Groups can be displayed as numbers on corresponding faces
	- Real-time in Edit Mode


Customized FBX Exporter:
------------------------

	- Can export everything from the above addons
	- Can calculate and export tangents and binormals
	- Optional support to export normals generated by asdn's Recalc Vertex Normals addon
	- UDK-specific optimiztions:
		-- b_root is now exported as root bone instead of the exporter creating a new one
		-- limited axis flip settings to things that make sense and labeled them
		-- tangents are very close to what UDK automatically generates


