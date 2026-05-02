#===========================================================
# iEDA 布局脚本 - PicoRV32
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
##   read def from floorplan
#===========================================================
def_init -path $::env(RESULT_DIR)/iFP_result.def

#===========================================================
##   optional placement blockages for congestion experiments
#===========================================================
proc apply_env_placement_blockages {} {
   set blockage_specs ""
   if {[info exists ::env(SILICONTRACE_PL_BLOCKAGES)] && $::env(SILICONTRACE_PL_BLOCKAGES) ne ""} {
      set blockage_specs $::env(SILICONTRACE_PL_BLOCKAGES)
   } elseif {[info exists ::env(PL_BLOCKAGES)] && $::env(PL_BLOCKAGES) ne ""} {
      set blockage_specs $::env(PL_BLOCKAGES)
   }

   if {$blockage_specs eq ""} {
      return
   }

   set applied_count 0
   foreach spec [split $blockage_specs ";"] {
      set spec [string trim $spec]
      if {$spec eq ""} {
         continue
      }

      set coords [split $spec ","]
      if {[llength $coords] != 4} {
         puts "Ignoring placement blockage with invalid box: $spec"
         continue
      }

      set clean_coords {}
      set valid_coords 1
      foreach coord $coords {
         set value [string trim $coord]
         if {![regexp {^-?[0-9]+$} $value]} {
            set valid_coords 0
            break
         }
         lappend clean_coords $value
      }
      if {!$valid_coords} {
         puts "Ignoring placement blockage with non-integer coordinate: $spec"
         continue
      }

      set box [join $clean_coords " "]
      if {[catch {add_placement_blockage -box $box} err]} {
         puts "Failed to add placement blockage '$spec': $err"
      } else {
         incr applied_count
      }
   }

   puts "Applied $applied_count placement blockage(s) from environment"
}

apply_env_placement_blockages

#===========================================================
##   run Placer
#===========================================================
set PL_CONFIG_PATH "$::env(CONFIG_DIR)/pl_default_config.json"
if {[info exists ::env(PL_CONFIG)] && $::env(PL_CONFIG) ne ""} {
   set PL_CONFIG_PATH $::env(PL_CONFIG)
}
run_placer -config $PL_CONFIG_PATH

#===========================================================
##   save def
#===========================================================
def_save -path $::env(RESULT_DIR)/iPL_result.def

#===========================================================
##   save netlist
#===========================================================
netlist_save -path $::env(RESULT_DIR)/iPL_result.v -exclude_cell_names {}

#===========================================================
##   report
#===========================================================
report_db -path "$::env(RESULT_DIR)/report/pl_db.rpt"

#===========================================================
##   Exit
#===========================================================
flow_exit
