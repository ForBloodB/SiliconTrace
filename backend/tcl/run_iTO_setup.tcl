#===========================================================
# iEDA Setup 优化脚本 - PicoRV32
#===========================================================

flow_init -config $::env(CONFIG_DIR)/flow_config.json
db_init -config $::env(CONFIG_DIR)/db_default_config.json -output_dir_path $::env(RESULT_DIR)

source $::env(CUSTOM_TCL_DIR)/db_path_setting.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lib_setup.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_sdc.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lef.tcl

if {[info exists ::env(INPUT_DEF)]} {
    set INPUT_DEF_PATH $::env(INPUT_DEF)
} else {
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iTO_hold_result.def"
}
def_init -path $INPUT_DEF_PATH

set TO_SETUP_CONFIG "$::env(CONFIG_DIR)/to_default_config_setup.json"
if {[info exists ::env(TO_SETUP_CONFIG)] && $::env(TO_SETUP_CONFIG) ne ""} {
    set TO_SETUP_CONFIG $::env(TO_SETUP_CONFIG)
}
run_to_setup -config $TO_SETUP_CONFIG
feature_tool -path $::env(RESULT_DIR)/feature/ito_optsetup.json -step optSetup

if {[info exists ::env(OUTPUT_DEF)]} {
    set OUTPUT_DEF_PATH $::env(OUTPUT_DEF)
} else {
    set OUTPUT_DEF_PATH "$::env(RESULT_DIR)/iTO_setup_result.def"
}
def_save -path $OUTPUT_DEF_PATH
netlist_save -path $::env(RESULT_DIR)/iTO_setup_result.v -exclude_cell_names {}

report_db -path "$::env(RESULT_DIR)/report/setup_db.rpt"
feature_summary -path $::env(RESULT_DIR)/feature/summary_ito_optsetup.json -step optSetup

flow_exit
