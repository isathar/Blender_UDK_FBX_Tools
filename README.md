Blender -> UE 3/4 FBX Tools

Blender addon that adds an editor for custom vertex normals, and an exporter with some tweaks and optimizations specific to the Unreal engine.
 
 
 
*Compatible with Blender v2.70+* 
 
_* A lot of this readme is obselete for version 1.0.0 *_ 


 
New Documentation coming soon. 
 
 
========================================================================================================= 
 
*Installation:* 
 
- Copy the 'udk_fbx_tools' folder to your addons directory.
- Find it in the Addon Manager in the 'Mesh' category as 'UE FBX Normals Tools' and enable it.
- There should be a new tab named 'Normals Editor' under 'Shading / UVs' in your tools panel. 
 
========================================================================================================= 
 
_*Notes:*_ 
 
 
_*v1.0.0*_ 
 
*Editor:* 
 
- The normals editor ui has been redesigned, and the documentation has not yet been updated :D 
 
- The export/import buttons have been moved to the standard export and import menus. 
 
- Auto Generation and 3D Line Display should now work in both Edit and Object modes.
  - Remaining mode limitations:
    - Object mode is required to use the Transfer function
    - Edit Mode is required for manual editing (for obvious reasons) 
 
- *Optional but extremely useful*: You'll need Vrav's Transfer Vertex Normals addon for the new Transfer Normals function. It's available at:
  - http://blenderartists.org/forum/showthread.php?259554-Addon-EditNormals-Transfer-Vertex-Normals&s=33911f74a3f9a2250b1645e4cda304a8 
 
- Custom normals can't be applied visually with shape keys or active modifiers.
  - They can still be edited, exported and displayed as lines. 
 
- When using poly mode (split) custom normals, the mesh must be triangulated before editing custom normals.
  - Vertex mode custom normals are not affected by triangulation and should export correctly after doing so. 
 
- Exporting with default tangents requires default normals and a triangulated mesh.
  - Without triangulation, one face will be reversed/split in the output.
  - The exporter will not export tangents if default tangents are selected with custom or automatic normals. 
 
- All bones in the armature must have deform enabled when using custom scale or axis settings with a skeletal mesh.
  - Bones without deform enabled will have weird scales and rotations.
  - This is relevant for applications that require the use of end bones.
  - Planned integration of leaf bone changes from the new official exporter should fix this. 
 
 
*Exporter:* 
 
- The importer currently works with FBX 6.1 ASCII files only. 
 
- New feature: Merge Vertex Colors:
  - Selecting this during export will export one vertex color layer consisting of all layers combined
  - This makes exporting vertex colors for wind effects and such easier. 
 
 
*Both:* 
 
- Minor changes to data structure used for normals:
  - Removed face center and vert position data.
  - Older files should still be compatible. 
 
 
*Displaying Normals on Meshes:* 
- Normals can be applied to the mesh in Vertex Mode, but not in Poly Mode. Both modes support displaying normals as 3D lines.
- The mesh's displayed normals will reset every time you enter Blender's Edit Mode, and can be reset by clicking _Apply to Mesh_ again.
 
 
*Export Time:* 
- Exporting Tangents and custom normals can take 2-4 times as long as default export modes (after lots of optimizations).
- Blender may freeze for a few seconds on complex meshes. 
 
 
*Editing Performance:* 
- I've tested the normals editor on meshes with up to 150000 polys.
- On my mid-range system, real-time display of normals is slow on anything past 25000 or so vertices.
- Checking "Selected Only" in the display section of each tool helps, but will slow things down more as you approach higher counts.
 
 
*Tangents and Unreal Engine 4:*
- Custom tangents are not calculculated using Mikk TSpace, so there will be a difference in shading when importing them to UE4.
- I've added the option to export Blender's tangents which should be identical to UE4's to but have the drawback of not accounting for custom normals. 
 
 
========================================================================================================= 

_Reference for tangent space calculation:_

Lengyel, Eric. “Computing Tangent Space Basis Vectors for an Arbitrary Mesh”. Terathon Software 3D Graphics Library, 2001. http://www.terathon.com/code/tangent.html

========================================================================================================= 


*Features:* 
 
_Editor for Vertex Normals:_ 
 
- Manual editing per poly or vertex normals
- Automatic generation with several presets for different scenarios
  - presets: (More advanced presets for foliage/tree normals should be up soon)
    - *Smooth* (Blender default)
    - *Vector*
    - *Bent* (facing away from 3d cursor by an adjustable ratio)
    - *Ground Foliage* (selected ground based vertices point up, everything else bent from an offset point)
    - *Custom* (similar to Blender's default normals with the ability to generate normals for selected faces as if they are disconnected)
- Allows calculating normals for selected faces or the whole mesh
- Normals can be displayed as lines for visual editing or applied to the mesh if in vertex mode 
 
 
_Customized FBX Exporter:_ 
 
- Can calculate and export tangents and binormals
- Can export custom normals from the included editor
- Support to export normals generated by asdn's Recalc Vertex Normals addon
- Unreal Engine 3/4-specific optimizations:
  - root bone fix that removes the armature bone from the exported file
    - root bone is now parented to the scene to stop weirdness with some software and UE physics
    - this fix also allows mesh orientations to be exported without having to mess around with the axis settings
  - new option to export default tangents (when using default normals)
  - custom tangents are pretty close to UDK's
- Exported meshes should now be fully compatible with nvidia's Apex Tools, xNormal and most other software that uses the FBX format
  - (previous versions caused crashes on import for some software) 
 
 
_Importer for Normals (FBX 6.1 files only):_ 
 
- Allows importing normals from FBX files to the custom variable used in this editor.
- Works with multiple meshes at the same time.
- The meshes have to already exist in the scene and be identical to the ones in the file (same number of vertices and faces). 
 
 
========================================================================================================= 
 
*Documentation:* 


- soon




========================================================================================================= 
Changelog: 


*1.0.0* (current) 
 
- finished 7.3 exporter for everything except Animations, Lamps, Cameras
- added remaining windowmanager variables to cleanup
- minor formatting changes to scripts
 
 
*1.0.0t5*
 
- fixed problem with previous release that broke skeletal mesh exports
- added ability to export combined vertex color layer
- readme updates 
 
 
*1.0.0t4* 
 
- added object mode support to Auto Generate and Display functions
- initial indexing system for FBX 7.3 files
- code formatting + UI optimizations
 
 
*1.0.0t3* 
 
- massive performance improvement to normals editor code by switching to a temp list for calculations/display 
 
 
*1.0.0t2* 
 
- added partially working fbx 7.3 exporter
- changed organization of 6.1 output files + added some exported variables 
 
 
*1.0.0t1* 
 
- removed redundant class for vertexn_meshdata list, switched to vert_data type
- moved import/export buttons to proper menus
- reorganized interface to decrease clutter
- fixed long-running typo of adsn's name :D 
 
- *exporter*:
- updated export scaling to a more standard method (not using local scaling)
- minor changes to previous armature axis settings fix (cleaner)
- updated default export method to read normals from loops like the newer default exporter
- added the ability to export blender's default tangents/binormals
- refactored + optimized custom tangent calculation method
  - performance improvements for exporting custom tangents (should be much faster now)
- added the ability to pick the UV layer tangents are based on (1 layer max)
- added warning messages + fallbacks to prevent the exporter from stopping when it encounters a problem 
  
- *editor*:
- added ability to use Vrav's Transfer Vertex Normals addon from editor
  - this replaces copy/paste functionality 
 
 
*0.10.1* 
 
- *exporter*:
- fixed scaling for static mesh exports, not working properly for armatures at the moment
- the exporter now detects the root bone of any parented armature, removing the need to manually enter root bone name
- fixed an export error that occured when exporting a mesh twice (the normals list was getting cleared if in vertex mode)
- *editor*:
- fixed Default auto-generation method 
 
 
*0.10.0* 
 
- replaced broken init file (Blender should recognize the addon again)
- added ability to switch between per-poly and vertex normals in editor
- added ability to apply normals to mesh (vertex mode only, no split normals)
- rewrote Custom auto-generation mode (much faster now, and less likely to produce bad results)
- added bending ratio to Bent auto-generation mode
- rewrote copy/paste functionality
- various fixes to armature export 
 
 
*0.9.0* 
 
- added importer for normals only
- *exporter:*
- more exporter performance improvements
- changed the way normals etc are exported
- removed vertex sorting stuff from normals export since it should all be handled by the editor now 
 
 
*0.8.0* 
 
- *exporter:*
- rewrote the armature bone fix to parent the root bone to the scene (the way the armature object was before)
  - exported files should now be compatible with nvidia apex tools and anything else that uses fbx
  - no more messing with UDK's imported mesh rotations
- changed the way axis settings are handled during export and set up separate axis options
- exporter speed improvements 
 
 
*0.7.5* 
 
- *editor:*
- fixed Custom (Angle-Based) auto-generation mode. 
  - It's slightly slower (as in, it can take about 5 min for a 3600 poly mesh), but should no longer produce weird results on complex meshes.
- fixed wrong vertex being selected while using manual edit (bad math)
- *exporter:*
- added check for UV layer before calculating tangents. If not found, the mesh is exported without tangents (default behavior) 


*0.7.0*

- initial release