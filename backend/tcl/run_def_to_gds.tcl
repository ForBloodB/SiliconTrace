#===========================================================
# iEDA GDSII 生成脚本 - PicoRV32
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
##   read lef
#===========================================================
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lef.tcl

#===========================================================
##   read def from routing
#===========================================================
set DEFAULT_INPUT_DEF "$::env(RESULT_DIR)/iRT_result.def"
def_init -path [expr {[info exists ::env(INPUT_DEF)] ? $::env(INPUT_DEF) : $DEFAULT_INPUT_DEF}]

#===========================================================
##   save GDSII
#===========================================================
gds_save -path $::env(RESULT_DIR)/picorv32.gds2

#===========================================================
##   save final def and netlist
#===========================================================
def_save -path $::env(RESULT_DIR)/final_design.def
netlist_save -path $::env(RESULT_DIR)/final_design.v

#===========================================================
##   Exit
#===========================================================
flow_exit
