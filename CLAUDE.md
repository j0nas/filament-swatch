# Filament Swatch Generator

Generates multi-color 3MF filament sample swatches for a Bambu Lab H2C printer.

## Usage

```bash
python generate_swatches.py "ABS,eSun,White" "PETG,BambuLab,Blue" "PLA,Polyalkemi,Black"
```

Each arg is `"Type,Producer,Color"` or `"Type,Producer,Color,#HEX"` for exact color. Options: `-o filename.3mf`, `--keep` (preserve temp files), `--openscad /path`.

## How it works

- Renders swatch body + text as separate STLs via OpenSCAD, assembles into a multi-part 3MF
- Maps color names to hex, picks black/white text based on body brightness (threshold 0.3)
- Optimizes filament slots by reusing body colors as text colors
- Maps filament types to H2C profiles, sets filament colors in project settings
- Opens the result in Bambu Studio

## Swatch design

100x36x2mm rounded rectangle. Left: 9 thickness-test cutouts (0.2-1.8mm) + prism + cylinder. Right: producer/type/color text in Arial Bold, auto-scaled.

## Dependencies

- Python 3.10+
- OpenSCAD (for text/geometry rendering)
- Bambu Studio (for opening the result)
