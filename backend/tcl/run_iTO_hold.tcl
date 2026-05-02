#===========================================================
# iEDA Hold 优化脚本 - PicoRV32
#===========================================================

flow_init -config $::env(CONFIG_DIR)/flow_config.json
db_init -config $::env(CONFIG_DIR)/db_default_config.json -output_dir_path $::env(RESULT_DIR)

source $::env(CUSTOM_TCL_DIR)/db_path_setting.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lib_hold.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_sdc.tcl
source $::env(TCL_SCRIPT_DIR)/DB_script/db_init_lef.tcl

if {[info exists ::env(INPUT_DEF)]} {
    set INPUT_DEF_PATH $::env(INPUT_DEF)
} else {
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iTO_drv_result.def"
}
def_init -path $INPUT_DEF_PATH

run_to_hold -config $::env(CONFIG_DIR)/to_default_config_hold.json
feature_tool -path $::env(RESULT_DIR)/feature/ito_opthold.json -step optHold

if {[info exists ::env(OUTPUT_DEF)]} {
    set OUTPUT_DEF_PATH $::env(OUTPUT_DEF)
} else {
    set OUTPUT_DEF_PATH "$::env(RESULT_DIR)/iTO_hold_result.def"
}
def_save -path $OUTPUT_DEF_PATH
netlist_save -path $::env(RESULT_DIR)/iTO_hold_result.v -exclude_cell_names {}

report_db -path "$::env(RESULT_DIR)/report/hold_db.rpt"
feature_summary -path $::env(RESULT_DIR)/feature/summary_ito_opthold.json -step optHold

flow_exit
