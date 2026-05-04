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
proc env_or_default {name default_value} {
   if {[info exists ::env($name)] && $::env($name) ne ""} {
      return $::env($name)
   }
   return $default_value
}

set BACKEND_PDK "sky130"
if {[info exists ::env(BACKEND_PDK)] && $::env(BACKEND_PDK) ne ""} {
   set BACKEND_PDK $::env(BACKEND_PDK)
}

if {$BACKEND_PDK eq "gf180"} {
   set PLACE_SITE GF018hv5v_mcu_sc7
   set IO_SITE GF018hv5v_mcu_sc7
   set CORNER_SITE GF018hv5v_mcu_sc7
   set PIN_LAYER Metal5
   set TAPCELL_NAME gf180mcu_fd_sc_mcu7t5v0__filltie
   set ENDCAP_NAME gf180mcu_fd_sc_mcu7t5v0__endcap
   set POWER_PIN_NAMES {VDD}
   set GROUND_PIN_NAMES {VSS}
   set PDN_GRID_LAYER Metal1
   set PDN_STRIPE_LAYER_1 Metal4
   set PDN_STRIPE_LAYER_2 Metal5
} else {
   set PLACE_SITE unithd
   set IO_SITE unithd
   set CORNER_SITE unithd
   set PIN_LAYER met5
   set TAPCELL_NAME sky130_fd_sc_hd__tap_1
   set ENDCAP_NAME sky130_fd_sc_hd__fill_1
   set POWER_PIN_NAMES {VPWR VPB vdd}
   set GROUND_PIN_NAMES {VGND VNB gnd}
   set PDN_GRID_LAYER met1
   set PDN_STRIPE_LAYER_1 met4
   set PDN_STRIPE_LAYER_2 met5
}

init_floorplan \
   -die_area $::env(DIE_AREA) \
   -core_area $::env(CORE_AREA) \
   -core_site $PLACE_SITE \
   -io_site $IO_SITE \
   -corner_site $CORNER_SITE

#===========================================================
##   create tracks
#===========================================================
if {$BACKEND_PDK eq "gf180"} {
   gern_track -layer Metal1 -x_start 280 -x_step 560 -y_start 280 -y_step 560
   gern_track -layer Metal2 -x_start 280 -x_step 560 -y_start 280 -y_step 560
   gern_track -layer Metal3 -x_start 280 -x_step 560 -y_start 280 -y_step 560
   gern_track -layer Metal4 -x_start 280 -x_step 560 -y_start 280 -y_step 560
   gern_track -layer Metal5 -x_start 450 -x_step 900 -y_start 450 -y_step 900
} else {
   gern_track -layer li1 -x_start 240 -x_step 480 -y_start 185 -y_step 370
   gern_track -layer met1 -x_start 185 -x_step 370 -y_start 185 -y_step 370
   gern_track -layer met2 -x_start 240 -x_step 480 -y_start 240 -y_step 480
   gern_track -layer met3 -x_start 370 -x_step 740 -y_start 370 -y_step 740
   gern_track -layer met4 -x_start 480 -x_step 960 -y_start 480 -y_step 960
   gern_track -layer met5 -x_start 185 -x_step 3330 -y_start 185 -y_step 3330
}

#===========================================================
##  add io port for pdn
#===========================================================
set PDN_ENABLE [env_or_default PDN_ENABLE 1]

if {$PDN_ENABLE ne "0"} {
   add_pdn_io -net_name VDD -direction INOUT -is_power 1
   add_pdn_io -net_name VSS -direction INOUT -is_power 0
} else {
   puts "PDN_ENABLE=0, skip VDD/VSS PDN IO ports"
}

#===========================================================
##  Place IO Port
#===========================================================
auto_place_pins -layer $PIN_LAYER -width 2000 -height 2000

#===========================================================
##   Tap Cell
#===========================================================
set TAPCELL_DISTANCE [env_or_default TAPCELL_DISTANCE 14]

tapcell \
   -tapcell $TAPCELL_NAME \
   -distance $TAPCELL_DISTANCE \
   -endcap $ENDCAP_NAME

#===========================================================
##   PDN
#===========================================================
set PDN_MET1_GRID_WIDTH [env_or_default PDN_MET1_GRID_WIDTH 0.48]
set PDN_MET4_STRIPE_WIDTH [env_or_default PDN_MET4_STRIPE_WIDTH 1.60]
set PDN_MET4_STRIPE_PITCH [env_or_default PDN_MET4_STRIPE_PITCH 27.14]
set PDN_MET4_STRIPE_OFFSET [env_or_default PDN_MET4_STRIPE_OFFSET 13.57]
set PDN_MET5_STRIPE_WIDTH [env_or_default PDN_MET5_STRIPE_WIDTH 1.60]
set PDN_MET5_STRIPE_PITCH [env_or_default PDN_MET5_STRIPE_PITCH 27.20]
set PDN_MET5_STRIPE_OFFSET [env_or_default PDN_MET5_STRIPE_OFFSET 13.60]
set PDN_ENABLE_GRID [env_or_default PDN_ENABLE_GRID 1]
set PDN_ENABLE_STRIPES [env_or_default PDN_ENABLE_STRIPES 1]

if {$PDN_ENABLE ne "0"} {
   foreach pin_name $POWER_PIN_NAMES {
      global_net_connect -net_name VDD -instance_pin_name $pin_name -is_power 1
   }
   foreach pin_name $GROUND_PIN_NAMES {
      global_net_connect -net_name VSS -instance_pin_name $pin_name -is_power 0
   }

   if {$PDN_ENABLE_GRID ne "0"} {
      create_grid -layer_name $PDN_GRID_LAYER -net_name_power VDD -net_name_ground VSS -width $PDN_MET1_GRID_WIDTH
   } else {
      puts "PDN_ENABLE_GRID=0, skip $PDN_GRID_LAYER PDN grid"
   }

   if {$PDN_ENABLE_STRIPES ne "0"} {
      create_stripe -layer_name $PDN_STRIPE_LAYER_1 -net_name_power VDD -net_name_ground VSS -width $PDN_MET4_STRIPE_WIDTH -pitch $PDN_MET4_STRIPE_PITCH -offset $PDN_MET4_STRIPE_OFFSET
      create_stripe -layer_name $PDN_STRIPE_LAYER_2 -net_name_power VDD -net_name_ground VSS -width $PDN_MET5_STRIPE_WIDTH -pitch $PDN_MET5_STRIPE_PITCH -offset $PDN_MET5_STRIPE_OFFSET

      if {$PDN_ENABLE_GRID ne "0"} {
         set connect1 "$PDN_GRID_LAYER $PDN_STRIPE_LAYER_1"
         set connect2 "$PDN_STRIPE_LAYER_1 $PDN_STRIPE_LAYER_2"
         connect_two_layer -layers [concat $connect1 $connect2]
      } else {
         connect_two_layer -layers "$PDN_STRIPE_LAYER_1 $PDN_STRIPE_LAYER_2"
      }
   } else {
      puts "PDN_ENABLE_STRIPES=0, skip $PDN_STRIPE_LAYER_1/$PDN_STRIPE_LAYER_2 PDN stripes"
   }
} else {
   puts "PDN_ENABLE=0, skip PDN global connections and grid"
}

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
