# Filament Swatch Generator

Generate multi-color filament sample swatches as ready-to-print Bambu Studio 3MF projects.

![swatch](https://github.com/user-attachments/assets/placeholder.png)

## Usage

```bash
python generate_swatches.py "ABS,eSun,White" "PETG,BambuLab,Blue" "PLA,Polyalkemi,Black"
```

Each argument is `Type,Producer,Color` -- optionally append `,#HEX` for exact color control.

The script renders the geometry via OpenSCAD, assembles a multi-part 3MF with correct filament profiles, and opens it in Bambu Studio.

## Swatch design

100x36x2mm rounded rectangle. Left half has thickness-test cutouts (0.2--1.8mm). Right half has producer/type/color text. Text color is automatically black or white based on body brightness.

## Requirements

- Python 3.10+
- [OpenSCAD](https://openscad.org/)
- [Bambu Studio](https://bambulab.com/en/download/studio)

## Printer

Built for the Bambu Lab H2C with 0.4mm nozzle. Edit `h2c_project_settings.config` and the profile maps in the script for other printers.
