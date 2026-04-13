text1="BambuLab";

text2="PLA Matte";

text3="Black";

/* [AdditionalSettings] */ 
text1_size=6;
text1_x=46.5;
text1_y=29;

text2_size=7;
text2_x=46.25;
text2_y=18;

text3_size=6;
text3_x=46.5;
text3_y=8;

text4="";
text4_size=3;
text4_x=46.5;
text4_y=6.5;

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
            points = [
                [0, 0],
                [base_width, 0],
                [0, height]
            ];
            faces = [
                [0, 1, 2]
            ];
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
    rectangle_cutout([50, 30, 0.2], [46.5, 3, 1.8]);
}

union() {

    extruded_text(text1, text1_size, 0.2, [text1_x, text1_y, 1.8], "Arial:style=Bold");
    extruded_text(text2, text2_size, 0.2, [text2_x, text2_y, 1.8], "Arial:style=Bold");
    extruded_text(text3, text3_size, 0.2, [text3_x, text3_y, 1.8], "Arial:style=Bold");
    extruded_text(text4, text4_size, 0.2, [text4_x, text4_y, 1.8], "Arial:style=Bold");
}
