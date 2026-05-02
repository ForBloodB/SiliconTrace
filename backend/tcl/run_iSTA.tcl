#===========================================================
# iEDA 静态时序分析脚本 - PicoRV32
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
##   reset lib
#===========================================================
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lib.tcl

#===========================================================
##   reset sdc
#===========================================================
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_sdc.tcl

#===========================================================
##   read lef
#===========================================================
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lef.tcl

#===========================================================
##   read spef when available
#===========================================================
if {[info exists ::env(SPEF_PATH)] && $::env(SPEF_PATH) ne ""} {
    source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_spef.tcl
}

#===========================================================
##   read def (from routing or CTS, depending on availability)
#===========================================================
set route_completed 0
set route_status_path "$::env(RESULT_DIR)/rt/route_status.txt"
if {[file exists $route_status_path]} {
    set route_status_file [open $route_status_path r]
    set route_status_data [read $route_status_file]
    close $route_status_file
    if {[string match "*status=success*" $route_status_data]} {
        set route_completed 1
    }
}

if {[info exists ::env(INPUT_DEF)]} {
    set INPUT_DEF_PATH $::env(INPUT_DEF)
} elseif {[file exists "$::env(RESULT_DIR)/iRT_result.def"]} {
    # Use routed DEF if it exists (even with DRC violations, routing data is valid for STA)
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iRT_result.def"
} elseif {[file exists "$::env(RESULT_DIR)/iTO_setup_result.def"]} {
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iTO_setup_result.def"
} elseif {[file exists "$::env(RESULT_DIR)/iTO_hold_result.def"]} {
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iTO_hold_result.def"
} else {
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iCTS_result.def"
}
def_init -path $INPUT_DEF_PATH

#===========================================================
##   run STA
#===========================================================
run_sta -output $::env(RESULT_DIR)/sta/

#===========================================================
##   Exit
#===========================================================
flow_exit
