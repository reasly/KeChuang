/*
  海鲜温度节点外置盒（可调参数）
  左边为底盒，右边为上盖；单位 mm。
  打印前务必用卡尺测量自己的扩展板和移动电源，并修改参数。
*/
$fn = 48;

inner_x = 122;          // 内部长度：扩展板 + 电池并排
inner_y = 74;           // 内部宽度
inner_z = 38;           // 内部高度
wall = 2.4;
floor_t = 2.8;
corner_r = 5;
lid_t = 2.4;
clearance = 0.35;

board_x = 58;           // RF Nano 扩展板实测长度
board_y = 54;           // RF Nano 扩展板实测宽度
board_hole_dx = 50;     // 安装孔中心距 X
board_hole_dy = 46;     // 安装孔中心距 Y
post_d = 6;
post_hole_d = 2.8;      // M3 自攻/热熔螺母前请试打
post_h = 6;

battery_x = 52;         // 小型成品 5V 移动电源预留
battery_y = 68;
gland_d = 12;           // 探头线防水接头孔；按 M10/M12 接头修改
usb_slot_w = 14;
usb_slot_h = 9;

outer_x = inner_x + 2 * wall;
outer_y = inner_y + 2 * wall;
outer_z = inner_z + floor_t;

module rounded_rect_2d(x, y, r) {
    hull() {
        for (px = [r, x-r], py = [r, y-r]) translate([px, py]) circle(r=r);
    }
}

module rounded_box(x, y, z, r) {
    linear_extrude(height=z) rounded_rect_2d(x, y, r);
}

module hollow_base() {
    difference() {
        union() {
            rounded_box(outer_x, outer_y, outer_z, corner_r);
            // 两侧扎带耳：将电子盒固定在泡沫箱外侧
            translate([-10, 14, 0]) cube([12, 18, 4]);
            translate([-10, outer_y-32, 0]) cube([12, 18, 4]);
            translate([outer_x-2, 14, 0]) cube([12, 18, 4]);
            translate([outer_x-2, outer_y-32, 0]) cube([12, 18, 4]);
        }
        translate([wall, wall, floor_t])
            rounded_box(inner_x, inner_y, inner_z + 2, max(1, corner_r-wall));
        // 扎带槽
        for (px = [-7, outer_x+3], py = [18, outer_y-28])
            translate([px, py, -1]) cube([4, 10, 7]);
        // DS18B20 探头线防水接头孔（短边）
        translate([-1, outer_y/2, floor_t+20])
            rotate([0,90,0]) cylinder(d=gland_d, h=wall+3);
        // USB 充电/调试开口（长边）
        translate([18, -1, floor_t+11]) cube([usb_slot_w, wall+3, usb_slot_h]);
    }
}

module standoff(x, y) {
    difference() {
        translate([x, y, floor_t]) cylinder(d=post_d, h=post_h);
        translate([x, y, floor_t-0.2]) cylinder(d=post_hole_d, h=post_h+0.5);
    }
}

module base_complete() {
    union() {
        hollow_base();
        // 扩展板四个支撑柱（左侧区域）
        board_origin_x = wall + 7;
        board_origin_y = wall + (inner_y-board_y)/2;
        for (px = [board_origin_x+4, board_origin_x+4+board_hole_dx],
             py = [board_origin_y+4, board_origin_y+4+board_hole_dy]) standoff(px, py);
        // 电池分隔筋和两条防滑筋（右侧区域）
        translate([wall+board_x+8, wall+3, floor_t]) cube([2, inner_y-6, 15]);
        translate([wall+board_x+13, wall+5, floor_t]) cube([battery_x-7, 2, 2]);
        translate([wall+board_x+13, outer_y-wall-7, floor_t]) cube([battery_x-7, 2, 2]);
    }
}

module lid() {
    difference() {
        union() {
            rounded_box(outer_x, outer_y, lid_t, corner_r);
            // 向内插入的定位边，预留打印间隙
            translate([wall+clearance, wall+clearance, lid_t])
                difference() {
                    rounded_box(inner_x-2*clearance, inner_y-2*clearance, 4, max(1, corner_r-wall));
                    translate([1.6,1.6,-0.1])
                        rounded_box(inner_x-2*clearance-3.2, inner_y-2*clearance-3.2, 4.3, 1);
                }
        }
        // 通气仅用于外壳内部散热，不代表防水；安装时孔朝下
        for (x = [44:10:84]) translate([x, outer_y/2-1.2, -0.2]) cube([6,2.4,lid_t+0.5]);
    }
}

base_complete();
translate([outer_x + 18, 0, 0]) lid();
