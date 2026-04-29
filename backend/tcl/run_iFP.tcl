#===========================================================
# iEDA 布局规划脚本 - PicoRV32
# 硅迹开源 (SiliconTrace Open)
#===========================================================

#===========================================================
##   init flow config
#===========================================================
flow_init -config $::env(CONFIG_DIR)/flow_config.json

#===========================================================
##   read db config
#===========================================================
db_init -config $::env(CONFIG_DIR)/db_default_config.json -output_dir_path $::env(RESULT_DIR)

#===========================================================
##   reset data path
#===========================================================
source $::env(CUSTOM_TCL_DIR)/db_path_setting.tcl

#===========================================================
##   read tech lef and lef
#===========================================================
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lef.tcl

#===========================================================
##   read verilog
#===========================================================
verilog_init -path $::env(NETLIST_FILE) -top $::env(DESIGN_TOP)

#===========================================================
##   init floorplan
#===========================================================
set PLACE_SITE unithd
set IO_SITE unithd
set CORNER_SITE unithd

init_floorplan \
   -die_area $::env(DIE_AREA) \
   -core_area $::env(CORE_AREA) \
   -core_site $PLACE_SITE \
   -io_site $IO_SITE \
   -corner_site $CORNER_SITE

#===========================================================
##   create tracks
#===========================================================
gern_track -layer li1 -x_start 240 -x_step 480 -y_start 185 -y_step 370
gern_track -layer met1 -x_start 185 -x_step 370 -y_start 185 -y_step 370
gern_track -layer met2 -x_start 240 -x_step 480 -y_start 240 -y_step 480
gern_track -layer met3 -x_start 370 -x_step 740 -y_start 370 -y_step 740
gern_track -layer met4 -x_start 480 -x_step 960 -y_start 480 -y_step 960
gern_track -layer met5 -x_start 185 -x_step 3330 -y_start 185 -y_step 3330

#===========================================================
##  add io port for pdn
#===========================================================
add_pdn_io -net_name VDD -direction INOUT -is_power 1
add_pdn_io -net_name VSS -direction INOUT -is_power 0

#===========================================================
##  Place IO Port
#===========================================================
auto_place_pins -layer met5 -width 2000 -height 2000

#===========================================================
##   Tap Cell
#===========================================================
tapcell \
   -tapcell sky130_fd_sc_hd__tap_1 \
   -distance 14 \
   -endcap sky130_fd_sc_hd__fill_1

#===========================================================
##   PDN
#===========================================================
global_net_connect -net_name VDD -instance_pin_name VPWR -is_power 1
global_net_connect -net_name VDD -instance_pin_name VPB  -is_power 1
global_net_connect -net_name VDD -instance_pin_name vdd  -is_power 1
global_net_connect -net_name VSS -instance_pin_name VGND -is_power 0
global_net_connect -net_name VSS -instance_pin_name VNB  -is_power 0
global_net_connect -net_name VSS -instance_pin_name gnd  -is_power 0

create_grid -layer_name met1 -net_name_power VDD -net_name_ground VSS -width 0.48

create_stripe -layer_name met4 -net_name_power VDD -net_name_ground VSS -width 1.60 -pitch 27.14 -offset 13.57
create_stripe -layer_name met5 -net_name_power VDD -net_name_ground VSS -width 1.60 -pitch 27.20 -offset 13.60

set connect1 "met1 met4"
set connect2 "met4 met5"
connect_two_layer -layers [concat $connect1 $connect2]

#===========================================================
##   set clock net
#===========================================================
set_net -net_name clk -type CLOCK

#===========================================================
##   save def
#===========================================================
def_save -path $::env(RESULT_DIR)/iFP_result.def

#===========================================================
##   report db summary
#===========================================================
report_db -path "$::env(RESULT_DIR)/report/fp_db.rpt"

#===========================================================
##   Exit
#===========================================================
flow_exit
