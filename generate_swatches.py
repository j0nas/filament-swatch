#!/usr/bin/env python3
"""Generate multi-color filament sample swatches as a ready-to-print 3MF.

Usage:
    python generate_swatches.py "ABS+,eSun,White" "ABS+,eSun,Purple" "ABS,efilament3d.pl,Black"

Each argument is a "Type,Producer,Color" tuple (optionally "Type,Producer,Color,#HEX").
The script auto-assigns filament colors, picks black or white text per swatch based
on brightness, and optimizes filament slots by reusing body colors as text colors.
"""

import argparse
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

BAMBU_STUDIO_SEARCH_PATHS = [
    # Windows
    Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe"),
    # macOS
    Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
    # Linux (flatpak & common)
    Path.home() / ".local/share/flatpak/exports/bin/com.bambulab.BambuStudio",
    Path("/usr/bin/bambu-studio"),
]

OPENSCAD_SEARCH_PATHS = [
    # Windows
    Path(r"C:\Program Files\OpenSCAD\openscad.exe"),
    Path(r"C:\Program Files (x86)\OpenSCAD\openscad.exe"),
    # macOS
    Path("/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"),
    # Linux
    Path("/usr/bin/openscad"),
    Path("/usr/local/bin/openscad"),
]

# ── Color mapping ──────────────────────────────────────────────────────────

COLOR_MAP = {
    "black":        "#161616",
    "white":        "#FFFFFF",
    "red":          "#E42C2C",
    "blue":         "#2C5EE4",
    "green":        "#0ACC38",
    "yellow":       "#F5E642",
    "orange":       "#F5A623",
    "purple":       "#A03CF7",
    "pink":         "#F95D73",
    "grey":         "#888888",
    "gray":         "#888888",
    "silver":       "#C0C0C0",
    "gold":         "#D4A843",
    "brown":        "#6B3A2A",
    "beige":        "#D9C8A5",
    "cream":        "#FFFDD0",
    "ivory":        "#FFFFF0",
    "navy":         "#1B2A5C",
    "teal":         "#2A9D8F",
    "cyan":         "#00BCD4",
    "magenta":      "#E91E8C",
    "maroon":       "#5C1B1B",
    "olive":        "#6B8E23",
    "lime":         "#7ED321",
    "coral":        "#FF6F61",
    "salmon":       "#FA8072",
    "tan":          "#D2B48C",
    "turquoise":    "#40E0D0",
    "violet":       "#7B2D8E",
    "lavender":     "#B57EDC",
    "mint":         "#98FF98",
    "peach":        "#FFDAB9",
    "rose":         "#E8909C",
    "rose gold":    "#B76E79",
    "bronze":       "#CD7F32",
    "burgundy":     "#6B1D2A",
    "charcoal":     "#333333",
    "aurora green":  "#2E8B57",
    "dark green":   "#1B5E20",
    "dark blue":    "#1A237E",
    "dark red":     "#8B0000",
    "light blue":   "#90CAF9",
    "light green":  "#A5D6A7",
    "light grey":   "#CCCCCC",
    "light gray":   "#CCCCCC",
    "natural":      "#E8DCC8",
    "transparent":  "#E0E0E0",
    "clear":        "#E0E0E0",
    "neon green":   "#39FF14",
    "neon orange":  "#FF6600",
    "neon pink":    "#FF1493",
    "neon yellow":  "#DFFF00",
    "glitter flake":"#C0C0C0",
    "silk gold":    "#D4A843",
    "silk silver":  "#C0C0C0",
    "silk copper":  "#B87333",
}

# Map filament type keywords to Bambu Studio profile names
FILAMENT_PROFILE_MAP = {
    "ABS":          "Generic ABS @BBL H2C 0.4 nozzle",
    "ABS+":         "Generic ABS @BBL H2C 0.4 nozzle",
    "ASA":          "Generic ASA @BBL H2C 0.4 nozzle",
    "PETG":         "Generic PETG @BBL H2C 0.4 nozzle",
    "PETG HF":      "Generic PETG HF @BBL H2C 0.4 nozzle",
    "PETG-CF":      "Generic PETG-CF @BBL H2C 0.4 nozzle",
    "PLA":          "Generic PLA @BBL H2C 0.4 nozzle",
    "PLA Matte":    "Generic PLA @BBL H2C 0.4 nozzle",
    "PLA Silk":     "Generic PLA Silk @BBL H2C 0.4 nozzle",
    "PLA-CF":       "Generic PLA-CF @BBL H2C 0.4 nozzle",
    "PLA High Speed":"Generic PLA High Speed @BBL H2C 0.4 nozzle",
    "HTPLA":        "Generic PLA @BBL H2C 0.4 nozzle",
    "eSilk PLA":    "Generic PLA Silk @BBL H2C 0.4 nozzle",
    "TPU":          "Generic TPU @BBL H2C 0.4 nozzle",
    "PA":           "Generic PA @BBL H2C 0.4 nozzle",
    "PA-CF":        "Generic PA-CF @BBL H2C 0.4 nozzle",
    "PC":           "Generic PC @BBL H2C 0.4 nozzle",
    "HIPS":         "Generic HIPS @BBL H2C 0.4 nozzle",
    "Z-HIPS":       "Generic HIPS @BBL H2C 0.4 nozzle",
    "PVA":          "Generic PVA @BBL H2C 0.4 nozzle",
}

# Map filament type keywords to the base type Bambu Studio uses internally
FILAMENT_TYPE_MAP = {
    "ABS":          "ABS",
    "ABS+":         "ABS",
    "ASA":          "ASA",
    "PETG":         "PETG",
    "PETG HF":      "PETG",
    "PETG-CF":      "PETG-CF",
    "PLA":          "PLA",
    "PLA Matte":    "PLA",
    "PLA Silk":     "PLA",
    "PLA-CF":       "PLA-CF",
    "PLA High Speed":"PLA",
    "HTPLA":        "PLA",
    "eSilk PLA":    "PLA",
    "TPU":          "TPU",
    "PA":           "PA",
    "PA-CF":        "PA-CF",
    "PC":           "PC",
    "HIPS":         "HIPS",
    "Z-HIPS":       "HIPS",
    "PVA":          "PVA",
}

BLACK_HEX = "#161616"
WHITE_HEX = "#FFFFFF"


def color_to_hex(name: str) -> str:
    """Map a color name to a hex code. Returns the name if it's already a hex code."""
    if name.startswith("#") and len(name) in (4, 7):
        return name.upper()
    key = name.lower().strip()
    if key in COLOR_MAP:
        return COLOR_MAP[key]
    # Try partial match
    for k, v in COLOR_MAP.items():
        if k in key or key in k:
            return v
    print(f"  Warning: unknown color '{name}', using gray")
    return "#888888"


def perceived_brightness(hex_color: str) -> float:
    """Return 0.0 (black) to 1.0 (white) perceived brightness."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # ITU-R BT.601 luma
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def text_color_for(body_hex: str) -> str:
    """Pick black or white text based on body brightness."""
    return BLACK_HEX if perceived_brightness(body_hex) > 0.3 else WHITE_HEX


def filament_base_type(ftype: str) -> str:
    return FILAMENT_TYPE_MAP.get(ftype, "PLA")


def filament_profile(ftype: str) -> str:
    return FILAMENT_PROFILE_MAP.get(ftype, "Generic PLA @BBL H2C 0.4 nozzle")


# ── OpenSCAD templates ──────────────────────────────────────────────────────

SCAD_MODULES = r'''
module rounded_cube(size, radius, height) {
    hull() {
        translate([radius, radius, 0])
            cylinder(h = height, r = radius, $fn = 100);
        translate([size[0] - radius, radius, 0])
            cylinder(h = height, r = radius, $fn = 100);
        translate([radius, size[1] - radius, 0])
            cylinder(h = height, r = radius, $fn = 100);
        translate([size[0] - radius, size[1] - radius, 0])
            cylinder(h = height, r = radius, $fn = 100);
    }
}

module triangular_prism(base_width, height, prism_height, pos, rot) {
    translate(pos) {
        rotate(rot) {
            points = [ [0, 0], [base_width, 0], [0, height] ];
            faces = [ [0, 1, 2] ];
            linear_extrude(height = prism_height)
                polygon(points, faces);
        }
    }
}

module cylinder_cutout(r, h, pos) {
    translate(pos)
        cylinder(h = h, r = r, center = true, $fn = 100);
}

module rectangle_cutout(size, pos, rot = [0, 0, 0]) {
    translate(pos) {
        rotate(rot) {
            cube(size, center = false);
        }
    }
}

module extruded_text(text_string, text_size, height, position, font="Arial:style=Bold") {
    translate(position) {
        linear_extrude(height = height)
            text(text_string, size = text_size, font = font, halign = "left", valign = "center");
    }
}
'''

SCAD_BODY = SCAD_MODULES + r'''
difference() {
    rounded_cube([100, 36], 3, 2);

    rectangle_cutout([10, 20, 0.2], [2.5, 8, 1.8]);
    triangular_prism(1.6, 20, 10, [12.5, 28, 1.8], [0, 90, 180]);
    cylinder_cutout(5, 0.2, [7.5, 8, 1.9]);
    cylinder_cutout(5, 2, [7.5, 28, 1]);
    rectangle_cutout([10, 10, 1.8], [14.5, 23, 0.2]);
    rectangle_cutout([10, 10, 1.6], [14.5, 13, 0.4]);
    rectangle_cutout([10, 10, 1.4], [14.5, 3, 0.6]);
    rectangle_cutout([10, 10, 1.2], [24.5, 3, 0.8]);
    rectangle_cutout([10, 10, 1.0], [24.5, 13, 1.0]);
    rectangle_cutout([10, 10, 0.8], [24.5, 23, 1.2]);
    rectangle_cutout([10, 10, 0.6], [34.5, 23, 1.4]);
    rectangle_cutout([10, 10, 0.4], [34.5, 13, 1.6]);
    rectangle_cutout([10, 10, 0.2], [34.5, 3, 1.8]);
    rectangle_cutout([50, 30, 0.4], [46.5, 3, 1.6]);
}
'''

def _text_scad(producer: str, filament_type: str, color: str,
               sz1: float, sz2: float, sz3: float) -> str:
    return SCAD_MODULES + f'''
union() {{
    extruded_text("{producer}", {sz1}, 0.8, [48.5, 28, 1.2], "Arial:style=Bold");
    extruded_text("{filament_type}", {sz2}, 0.8, [48.5, 18, 1.2], "Arial:style=Bold");
    extruded_text("{color}", {sz3}, 0.8, [48.5, 8, 1.2], "Arial:style=Bold");
}}
'''

# ── Helpers ──────────────────────────────────────────────────────────────────

def find_openscad(override: str | None = None) -> Path:
    if override:
        p = Path(override)
        if p.is_file():
            return p
        raise FileNotFoundError(f"OpenSCAD not found at: {override}")
    found = shutil.which("openscad")
    if found:
        return Path(found)
    for p in OPENSCAD_SEARCH_PATHS:
        if p.is_file():
            return p
    raise FileNotFoundError(
        "OpenSCAD not found. Install with: winget install OpenSCAD.OpenSCAD"
    )


def find_bambu_studio() -> Path | None:
    found = shutil.which("bambu-studio") or shutil.which("BambuStudio")
    if found:
        return Path(found)
    for p in BAMBU_STUDIO_SEARCH_PATHS:
        if p.is_file():
            return p
    return None


TEXT_AREA_X_MIN = 48.5  # 46.5mm text area start + 2mm padding
TEXT_AREA_X_MAX = 95.0  # 100mm swatch - 3mm corner radius - 2mm padding


def scale_text_mesh(
    verts: list[tuple[float, float, float]],
    tris: list[tuple[int, int, int]],
) -> list[tuple[float, float, float]]:
    """Scale each text line independently to fit within the text area.

    Lines are identified by Y coordinate (producer ~28, type ~18, color ~8).
    Each line scales uniformly only if it overflows, anchored vertically:
      - producer: top-aligned (top edge stays put)
      - type: center-aligned
      - color: bottom-aligned (bottom edge stays put)
    """
    if not verts:
        return verts

    result = list(verts)
    target_width = TEXT_AREA_X_MAX - TEXT_AREA_X_MIN

    # (y_lo, y_hi, vertical anchor mode)
    lines = [
        (23, 999, "top"),      # producer at y≈28
        (13, 23,  "center"),   # type at y≈18
        (-999, 13, "bottom"),  # color at y≈8
    ]

    for y_lo, y_hi, anchor in lines:
        indices = [i for i, (_, y, _) in enumerate(verts) if y_lo <= y <= y_hi]
        if not indices:
            continue

        line_max_x = max(verts[i][0] for i in indices)
        if line_max_x <= TEXT_AREA_X_MAX:
            continue

        actual_width = line_max_x - TEXT_AREA_X_MIN
        s = target_width / actual_width

        ys = [verts[i][1] for i in indices]
        if anchor == "top":
            ay = max(ys)
        elif anchor == "bottom":
            ay = min(ys)
        else:
            ay = (min(ys) + max(ys)) / 2

        for i in indices:
            x, y, z = verts[i]
            result[i] = (
                TEXT_AREA_X_MIN + (x - TEXT_AREA_X_MIN) * s,
                ay + (y - ay) * s,
                z,
            )

    return result


def escape_scad(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def generate_text_scad(producer: str, filament_type: str, color: str) -> str:
    return _text_scad(
        escape_scad(producer), escape_scad(filament_type), escape_scad(color),
        6, 7, 6,
    )


def render_stl(scad_path: Path, stl_path: Path, openscad_exe: Path) -> None:
    result = subprocess.run(
        [str(openscad_exe), "-o", str(stl_path), str(scad_path)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"  OpenSCAD error:\n{result.stderr}", file=sys.stderr)
        raise RuntimeError(f"OpenSCAD failed for {scad_path.name}")


# ── Filament slot planning ──────────────────────────────────────────────────

def plan_filament_slots(swatches: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Compute filament slot assignments. Returns (swatches_with_slots, slots).
    Each slot: {"hex": "#...", "type": "ABS", "profile": "Generic ABS @..."}
    Reuses body filaments as text colors when possible.
    """
    # Determine body and text hex colors for each swatch
    for sw in swatches:
        sw["body_hex"] = color_to_hex(sw["color"])
        sw["text_hex"] = text_color_for(sw["body_hex"])

    # Collect unique colors needed
    color_to_swatch_type = {}  # hex -> filament type (for profile assignment)
    for sw in swatches:
        if sw["body_hex"] not in color_to_swatch_type:
            color_to_swatch_type[sw["body_hex"]] = sw["filament_type"]
    # Text-only colors: use the majority filament type across all swatches
    # (the text filament is generic, so match whatever you have most of)
    from collections import Counter
    type_counts = Counter(sw["filament_type"] for sw in swatches)
    majority_type = type_counts.most_common(1)[0][0]
    for sw in swatches:
        if sw["text_hex"] not in color_to_swatch_type:
            color_to_swatch_type[sw["text_hex"]] = majority_type

    unique_colors = list(color_to_swatch_type.keys())
    slots = []
    color_to_slot = {}
    for hex_color in unique_colors:
        ftype = color_to_swatch_type[hex_color]
        slot_idx = len(slots) + 1  # 1-based
        slots.append({
            "hex": hex_color,
            "type": filament_base_type(ftype),
            "profile": filament_profile(ftype),
        })
        color_to_slot[hex_color] = slot_idx

    for sw in swatches:
        sw["body_slot"] = color_to_slot[sw["body_hex"]]
        sw["text_slot"] = color_to_slot[sw["text_hex"]]

    return swatches, slots


# ── STL → 3MF mesh conversion ───────────────────────────────────────────────

def read_stl(path: Path) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Read an STL (ASCII or binary) and return deduplicated (vertices, triangles)."""
    data = path.read_bytes()
    is_ascii = data.lstrip().startswith(b"solid") and b"facet" in data[:1000]

    vertex_map: dict[tuple[float, float, float], int] = {}
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []

    def add_vertex(pt: tuple[float, float, float]) -> int:
        if pt not in vertex_map:
            vertex_map[pt] = len(vertices)
            vertices.append(pt)
        return vertex_map[pt]

    if is_ascii:
        text = data.decode("ascii", errors="replace")
        tri_verts = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("vertex"):
                parts = stripped.split()
                pt = (float(parts[1]), float(parts[2]), float(parts[3]))
                tri_verts.append(add_vertex(pt))
                if len(tri_verts) == 3:
                    triangles.append(tuple(tri_verts))
                    tri_verts = []
    else:
        num_triangles = struct.unpack_from("<I", data, 80)[0]
        offset = 84
        for _ in range(num_triangles):
            v = struct.unpack_from("<12f", data, offset)
            offset += 50
            tri_indices = []
            for j in range(3):
                pt = (v[3 + j * 3], v[4 + j * 3], v[5 + j * 3])
                tri_indices.append(add_vertex(pt))
            triangles.append(tuple(tri_indices))

    return vertices, triangles


def mesh_to_xml_str(obj_id: int, obj_uuid: str, vertices, triangles) -> str:
    """Build a 3MF <object> XML string with mesh data."""
    lines = [f'  <object id="{obj_id}" p:UUID="{obj_uuid}" type="model">',
             '   <mesh>', '    <vertices>']
    for x, y, z in vertices:
        lines.append(f'     <vertex x="{x}" y="{y}" z="{z}"/>')
    lines.append('    </vertices>')
    lines.append('    <triangles>')
    for v1, v2, v3 in triangles:
        lines.append(f'     <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>')
    lines.append('    </triangles>')
    lines.append('   </mesh>')
    lines.append('  </object>')
    return "\n".join(lines)


# ── 3MF assembly ────────────────────────────────────────────────────────────

MODEL_HEADER = '''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">'''


def make_uuid() -> str:
    return str(uuid.uuid4())


def build_3mf(
    swatches: list[dict],
    slots: list[dict],
    output_path: Path,
    tmpdir: Path,
) -> None:
    """Build a multi-color 3MF with correct filament slot assignments."""
    object_files = []
    top_objects = []
    next_id = 1
    swatch_spacing_y = 40
    plate_center_x = 162.5

    for i, sw in enumerate(swatches):
        body_verts, body_tris = read_stl(sw["body_stl"])
        text_verts, text_tris = read_stl(sw["text_stl"])
        text_verts = scale_text_mesh(text_verts, text_tris)

        body_id = next_id
        body_uuid = make_uuid()
        text_id = next_id + 1
        text_uuid = make_uuid()
        next_id += 2

        body_xml = mesh_to_xml_str(body_id, body_uuid, body_verts, body_tris)
        text_xml = mesh_to_xml_str(text_id, text_uuid, text_verts, text_tris)

        obj_file_content = f"""{MODEL_HEADER}
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <resources>
{body_xml}
{text_xml}
 </resources>
 <build/>
</model>"""

        obj_filename = f"object_{i + 1}.model"
        object_files.append((obj_filename, obj_file_content))

        top_id = next_id
        top_uuid = make_uuid()
        next_id += 1

        top_objects.append({
            "id": top_id,
            "uuid": top_uuid,
            "obj_file": obj_filename,
            "body_id": body_id,
            "body_uuid": make_uuid(),
            "text_id": text_id,
            "text_uuid": make_uuid(),
            "swatch": sw,
            "index": i,
        })

    # ── Main 3dmodel.model ──
    obj_lines = []
    build_lines = []
    for top in top_objects:
        obj_lines.append(f'  <object id="{top["id"]}" p:UUID="{top["uuid"]}" type="model">')
        obj_lines.append('   <components>')
        obj_lines.append(f'    <component p:path="/3D/Objects/{top["obj_file"]}" objectid="{top["body_id"]}" p:UUID="{top["body_uuid"]}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>')
        obj_lines.append(f'    <component p:path="/3D/Objects/{top["obj_file"]}" objectid="{top["text_id"]}" p:UUID="{top["text_uuid"]}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>')
        obj_lines.append('   </components>')
        obj_lines.append('  </object>')

        y_pos = 100 + top["index"] * swatch_spacing_y
        build_lines.append(f'  <item objectid="{top["id"]}" p:UUID="{make_uuid()}" transform="1 0 0 0 1 0 0 0 1 {plate_center_x} {y_pos} 0" printable="1"/>')

    today = datetime.now().strftime("%Y-%m-%d")
    main_model = f"""{MODEL_HEADER}
 <metadata name="Application">BambuStudio-02.05.00.66</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <metadata name="Copyright"></metadata>
 <metadata name="CreationDate">{today}</metadata>
 <metadata name="Description"></metadata>
 <metadata name="Designer"></metadata>
 <metadata name="DesignerCover"></metadata>
 <metadata name="DesignerUserId"></metadata>
 <metadata name="License"></metadata>
 <metadata name="ModificationDate">{today}</metadata>
 <metadata name="Origin"></metadata>
 <metadata name="ProfileCover"></metadata>
 <metadata name="ProfileDescription"></metadata>
 <metadata name="ProfileTitle"></metadata>
 <metadata name="Title">Filament Swatches</metadata>
 <resources>
{chr(10).join(obj_lines)}
 </resources>
 <build p:UUID="{make_uuid()}">
{chr(10).join(build_lines)}
 </build>
</model>"""

    # ── model_settings.config ──
    settings_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    for top in top_objects:
        sw = top["swatch"]
        name = f"{sw['producer']} {sw['filament_type']} {sw['color']}"
        settings_lines.append(f'  <object id="{top["id"]}">')
        settings_lines.append(f'    <metadata key="name" value="{name}"/>')
        settings_lines.append(f'    <metadata key="extruder" value="{sw["body_slot"]}"/>')
        settings_lines.append(f'    <part id="{top["body_id"]}" subtype="normal_part">')
        settings_lines.append(f'      <metadata key="name" value="Body"/>')
        settings_lines.append(f'      <metadata key="extruder" value="{sw["body_slot"]}"/>')
        settings_lines.append(f'    </part>')
        settings_lines.append(f'    <part id="{top["text_id"]}" subtype="normal_part">')
        settings_lines.append(f'      <metadata key="name" value="Text"/>')
        settings_lines.append(f'      <metadata key="extruder" value="{sw["text_slot"]}"/>')
        settings_lines.append(f'    </part>')
        settings_lines.append(f'  </object>')
    settings_lines.append('</config>')
    settings_xml = "\n".join(settings_lines)

    # ── Packaging files ──
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>'''

    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>'''

    model_rels_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for idx, (obj_fn, _) in enumerate(object_files, 1):
        model_rels_lines.append(
            f' <Relationship Target="/3D/Objects/{obj_fn}" Id="rel-{idx}" '
            f'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
    model_rels_lines.append('</Relationships>')
    model_rels = "\n".join(model_rels_lines)

    slice_info = '''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value="02.05.00.66"/>
  </header>
</config>'''

    cut_info_lines = ['<?xml version="1.0" encoding="utf-8"?>', '<objects>']
    for top in top_objects:
        cut_info_lines.append(f' <object id="{top["index"] + 1}">')
        cut_info_lines.append(f'  <cut_id id="0" check_sum="1" connectors_cnt="0"/>')
        cut_info_lines.append(f' </object>')
    cut_info_lines.append('</objects>')
    cut_info = "\n".join(cut_info_lines)

    filament_seq = '{"plate_1":{"sequence":[]}}'

    # Load and patch project settings with filament info
    project_settings = None
    project_settings_path = SCRIPT_DIR / "h2c_project_settings.config"
    if project_settings_path.is_file():
        data = json.loads(project_settings_path.read_text(encoding="utf-8"))
        n = len(slots)
        data["filament_colour"] = [s["hex"] for s in slots]
        data["filament_type"] = [s["type"] for s in slots]
        data["filament_settings_id"] = [s["profile"] for s in slots]
        data["filament_vendor"] = ["Generic"] * n
        data["filament_ids"] = ["GFB99"] * n
        # Resize all array settings to match slot count
        for key, val in list(data.items()):
            if isinstance(val, list) and len(val) > 0 and all(isinstance(v, str) for v in val):
                if len(val) != n and key not in ("filament_colour", "filament_type",
                    "filament_settings_id", "filament_vendor", "filament_ids"):
                    if len(val) >= 1:
                        data[key] = [val[0]] * n
        project_settings = json.dumps(data, indent=4, ensure_ascii=False)

    # ── Write ZIP ──
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", main_model)
        zf.writestr("3D/_rels/3dmodel.model.rels", model_rels)
        for obj_fn, obj_xml in object_files:
            zf.writestr(f"3D/Objects/{obj_fn}", obj_xml)
        zf.writestr("Metadata/model_settings.config", settings_xml)
        zf.writestr("Metadata/slice_info.config", slice_info)
        zf.writestr("Metadata/cut_information.xml", cut_info)
        zf.writestr("Metadata/filament_sequence.json", filament_seq)
        if project_settings:
            zf.writestr("Metadata/project_settings.config", project_settings)


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_tuple(s: str) -> tuple[str, str, str, str | None]:
    parts = [p.strip() for p in s.split(",")]
    if len(parts) < 3:
        raise ValueError(f"Expected 'Type,Producer,Color[,#HEX]' but got: '{s}'")
    hex_override = parts[3] if len(parts) >= 4 else None
    return parts[0], parts[1], parts[2], hex_override


def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-color filament sample swatches as 3MF"
    )
    parser.add_argument(
        "swatches", nargs="+",
        help='"Type,Producer,Color" or "Type,Producer,Color,#HEX" tuples',
    )
    parser.add_argument("-o", "--output", help="Output 3MF filename")
    parser.add_argument("--openscad", help="Path to OpenSCAD executable")
    parser.add_argument("--keep", action="store_true", help="Keep intermediate files")
    args = parser.parse_args()

    openscad_exe = find_openscad(args.openscad)
    print(f"Using OpenSCAD: {openscad_exe}")

    tuples = [parse_tuple(s) for s in args.swatches]

    if args.output:
        output_name = args.output
    else:
        output_name = f"Swatches_{datetime.now():%Y%m%d_%H%M%S}.3mf"
    output_path = SCRIPT_DIR / output_name

    tmpdir = Path(tempfile.mkdtemp(prefix="swatches_"))

    # Write body .scad once (same for every swatch)
    body_scad_path = tmpdir / "body.scad"
    body_scad_path.write_text(SCAD_BODY)
    body_stl_path = tmpdir / "body.stl"

    print("Rendering swatch body ...", flush=True)
    render_stl(body_scad_path, body_stl_path, openscad_exe)

    swatch_data = []
    for i, (ftype, producer, color, hex_override) in enumerate(tuples, 1):
        text_scad = generate_text_scad(producer, ftype, color)
        text_scad_path = tmpdir / f"text_{i}.scad"
        text_stl_path = tmpdir / f"text_{i}.stl"
        text_scad_path.write_text(text_scad)

        print(f"[{i}/{len(tuples)}] Rendering text: {producer} / {ftype} / {color} ...", flush=True)
        render_stl(text_scad_path, text_stl_path, openscad_exe)

        sw = {
            "producer": producer,
            "filament_type": ftype,
            "color": color,
            "body_stl": body_stl_path,
            "text_stl": text_stl_path,
        }
        if hex_override:
            sw["color_override"] = hex_override
        swatch_data.append(sw)

    # Apply hex overrides before slot planning
    for sw in swatch_data:
        if "color_override" in sw:
            sw["color"] = sw.pop("color_override")  # will be used by color_to_hex

    # Plan filament slots
    swatch_data, slots = plan_filament_slots(swatch_data)

    print(f"\nBuilding 3MF with {len(swatch_data)} swatches ...", flush=True)
    build_3mf(swatch_data, slots, output_path, tmpdir)

    print(f"\nDone! Open in Bambu Studio:")
    print(f"  {output_path}")
    print(f"\nFilament slots ({len(slots)}):")
    for i, slot in enumerate(slots, 1):
        print(f"  Slot {i}: {slot['hex']}  ({slot['type']})")
    print(f"\nSwatch assignments:")
    for sw in swatch_data:
        text_label = "white" if sw["text_hex"] == WHITE_HEX else "black"
        print(f"  {sw['producer']} {sw['filament_type']} {sw['color']}: "
              f"body=slot {sw['body_slot']} ({sw['body_hex']}), "
              f"text=slot {sw['text_slot']} ({text_label})")

    if args.keep:
        print(f"\nIntermediate files: {tmpdir}")
    else:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Open in Bambu Studio
    bambu = find_bambu_studio()
    if bambu:
        subprocess.Popen([str(bambu), str(output_path)])
    else:
        print("\nBambu Studio not found — open the 3MF file manually.")


if __name__ == "__main__":
    main()
