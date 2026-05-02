#===========================================================
# Standalone placement congestion report
#===========================================================

flow_init -config $::env(CONFIG_DIR)/flow_config.json

db_init -config $::env(CONFIG_DIR)/db_default_config.json -output_dir_path $::env(RESULT_DIR)

source $::env(CUSTOM_TCL_DIR)/db_path_setting.tcl

source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lib.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_sdc.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lef.tcl

set INPUT_DEF "$::env(RESULT_DIR)/iPL_result.def"
if {[info exists ::env(INPUT_DEF)] && $::env(INPUT_DEF) ne ""} {
   set INPUT_DEF $::env(INPUT_DEF)
}

def_init -path $INPUT_DEF

file mkdir "$::env(RESULT_DIR)/report"
report_congestion -path "$::env(RESULT_DIR)/report/pl_congestion.rpt"

flow_exit
