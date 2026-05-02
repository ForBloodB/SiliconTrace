#===========================================================
# iEDA 布线脚本 - PicoRV32
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
##   read def from timing-optimized CTS result
#===========================================================
catch {file delete -force "$::env(RESULT_DIR)/rt"}
file mkdir "$::env(RESULT_DIR)/rt"
catch {file delete -force "$::env(RESULT_DIR)/iRT_result.def"}
catch {file delete -force "$::env(RESULT_DIR)/iRT_result.v"}
catch {file delete -force "$::env(RESULT_DIR)/iRT_partial.def"}
catch {file delete -force "$::env(RESULT_DIR)/iRT_partial.v"}
catch {file delete -force "$::env(RESULT_DIR)/rt/route_status.txt"}

if {[info exists ::env(INPUT_DEF)]} {
    set INPUT_DEF_PATH $::env(INPUT_DEF)
} elseif {[file exists "$::env(RESULT_DIR)/iTO_setup_result.def"]} {
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iTO_setup_result.def"
} else {
    set INPUT_DEF_PATH "$::env(RESULT_DIR)/iCTS_result.def"
}
def_init -path $INPUT_DEF_PATH

proc write_route_status {path status detail {drc_count ""}} {
    regsub -all {[\r\n]+} $detail { } detail
    set fh [open $path "w"]
    puts $fh "status=$status"
    if {$detail ne ""} {
        puts $fh "detail=$detail"
    }
    if {$drc_count ne ""} {
        puts $fh "route_drc_violations=$drc_count"
    }
    close $fh
}

proc extract_route_drc_violations {log_path} {
    if {![file exists $log_path]} {
        return ""
    }

    set fh [open $log_path r]
    set log_data [read $fh]
    close $fh

    set section ""
    set total 0
    foreach line [split $log_data "\n"] {
        if {[regexp {\|\s*within_net\s*\|} $line]} {
            set section "within"
            continue
        }
        if {[regexp {\|\s*among_net\s*\|} $line]} {
            set section "among"
            continue
        }
        if {$section ne ""} {
            set fields [split $line "|"]
            if {[llength $fields] > 1 && [string trim [lindex $fields 1]] eq "Total"} {
                set last_num ""
                foreach field [lrange $fields 2 end] {
                    set value [string trim $field]
                    if {[regexp {^[0-9]+$} $value]} {
                        set last_num $value
                    }
                }
                if {$last_num ne ""} {
                    set total [expr {$total + $last_num}]
                    set section ""
                }
            }
        }
    }

    return $total
}

proc apply_env_route_blockages {} {
    if {![info exists ::env(SILICONTRACE_RT_BLOCKAGES)] || $::env(SILICONTRACE_RT_BLOCKAGES) eq ""} {
        return
    }

    set applied_count 0
    foreach spec [split $::env(SILICONTRACE_RT_BLOCKAGES) ";"] {
        set spec [string trim $spec]
        if {$spec eq ""} {
            continue
        }

        set fields [split $spec ":"]
        if {[llength $fields] < 2 || [llength $fields] > 3} {
            puts "Ignoring malformed route blockage spec: $spec"
            continue
        }

        set layer [string trim [lindex $fields 0]]
        set coords [split [string trim [lindex $fields 1]] ","]
        set exceptpgnet 1
        if {[llength $fields] == 3 && [string trim [lindex $fields 2]] ne ""} {
            set exceptpgnet [string trim [lindex $fields 2]]
        }

        if {[llength $coords] != 4} {
            puts "Ignoring route blockage with invalid box: $spec"
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
            puts "Ignoring route blockage with non-integer coordinate: $spec"
            continue
        }

        set box [join $clean_coords " "]
        if {[catch {add_routing_blockage -layer $layer -box $box -exceptpgnet $exceptpgnet} err]} {
            puts "Failed to add route blockage '$spec': $err"
        } else {
            incr applied_count
        }
    }

    puts "Applied $applied_count route blockage(s) from SILICONTRACE_RT_BLOCKAGES"
}

#===========================================================
##   run Router
#===========================================================
apply_env_route_blockages

set BOTTOM_ROUTING_LAYER "met1"
if {[info exists ::env(BOTTOM_ROUTING_LAYER)] && $::env(BOTTOM_ROUTING_LAYER) ne ""} {
    set BOTTOM_ROUTING_LAYER $::env(BOTTOM_ROUTING_LAYER)
}

set TOP_ROUTING_LAYER "met5"
if {[info exists ::env(TOP_ROUTING_LAYER)] && $::env(TOP_ROUTING_LAYER) ne ""} {
    set TOP_ROUTING_LAYER $::env(TOP_ROUTING_LAYER)
}

init_rt -temp_directory_path "$::env(RESULT_DIR)/rt/" \
        -bottom_routing_layer $BOTTOM_ROUTING_LAYER \
        -top_routing_layer $TOP_ROUTING_LAYER \
        -thread_number 4 \
        -output_inter_result 1 \
        -enable_notification 0 \
        -enable_timing 0

set rt_success 1
set rt_error ""
if {[catch {run_rt} err]} {
    puts "Routing completed with errors: $err"
    set rt_success 0
    set rt_error $err
}

catch {feature_tool -path $::env(RESULT_DIR)/feature/irt.json -step route}
catch {destroy_rt}

set route_drc_violations [extract_route_drc_violations "$::env(RESULT_DIR)/rt/rt.log"]
if {$rt_success && $route_drc_violations ne "" && $route_drc_violations > 0} {
    set rt_success 0
    set rt_error "Routing completed with $route_drc_violations DRC violations"
}

#===========================================================
##   save routed or partial result
#===========================================================
set DEFAULT_OUTPUT_DEF "$::env(RESULT_DIR)/iRT_result.def"
if {[info exists ::env(OUTPUT_DEF)]} {
    set OUTPUT_DEF_PATH $::env(OUTPUT_DEF)
} else {
    set OUTPUT_DEF_PATH $DEFAULT_OUTPUT_DEF
}

if {$rt_success} {
    def_save -path $OUTPUT_DEF_PATH
    catch {netlist_save -path $::env(RESULT_DIR)/iRT_result.v -exclude_cell_names {}}
    write_route_status "$::env(RESULT_DIR)/rt/route_status.txt" "success" "Routing completed" $route_drc_violations
} else {
    # Routing completed but with DRC violations — still save the routed DEF
    # so downstream STA/GDS can use it (DRC violations are informational for those steps)
    def_save -path $OUTPUT_DEF_PATH
    catch {netlist_save -path $::env(RESULT_DIR)/iRT_result.v -exclude_cell_names {}}
    catch {def_save -path "$::env(RESULT_DIR)/iRT_partial.def"}
    catch {netlist_save -path $::env(RESULT_DIR)/iRT_partial.v -exclude_cell_names {}}
    write_route_status "$::env(RESULT_DIR)/rt/route_status.txt" "failed" $rt_error $route_drc_violations
}

#===========================================================
##   report db summary
#===========================================================
catch {report_db -path "$::env(RESULT_DIR)/report/rt_db.rpt"}
catch {feature_summary -path $::env(RESULT_DIR)/feature/summary_irt.json -step route}

#===========================================================
##   Exit
#===========================================================
flow_exit
