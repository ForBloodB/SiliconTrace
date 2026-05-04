#===========================================================
# 自定义路径设置 - 使用 HD（高密度）标准单元库
# 硅迹开源 (SiliconTrace Open)
#===========================================================

set BACKEND_PDK "sky130"
if {[info exists ::env(BACKEND_PDK)] && $::env(BACKEND_PDK) ne ""} {
    set BACKEND_PDK $::env(BACKEND_PDK)
}

set DB_LEF_PATH "$::env(FOUNDRY_DIR)/lef"
set DB_LIB_PATH "$::env(FOUNDRY_DIR)/lib"

#===========================================================
##   使用标准单元库
#===========================================================
set CELL_TYPE "HD"

if {$BACKEND_PDK eq "gf180"} {
    set DB_TECH_LEF_PATH "$::env(FOUNDRY_DIR)/techlef"
    set TECH_LEF_PATH "$DB_TECH_LEF_PATH/gf180mcu_fd_sc_mcu7t5v0__nom.tlef"
    set LEF_PATH "$DB_LEF_PATH/gf180mcu_fd_sc_mcu7t5v0.lef"
    set LIB_PATH "$DB_LIB_PATH/gf180mcu_fd_sc_mcu7t5v0__tt_025C_1v80.lib"
} else {
    #===========================================================
    ##   tech lef path
    #===========================================================
    set TECH_LEF_PATH "$DB_LEF_PATH/sky130_fd_sc_hd.tlef"

    #===========================================================
    ##   lef path
    #===========================================================
    set LEF_PATH "$DB_LEF_PATH/sky130_fd_sc_hd_merged.lef \
                $DB_LEF_PATH/sky130_ef_io__com_bus_slice_10um.lef \
                $DB_LEF_PATH/sky130_ef_io__com_bus_slice_1um.lef \
                $DB_LEF_PATH/sky130_ef_io__com_bus_slice_20um.lef \
                $DB_LEF_PATH/sky130_ef_io__com_bus_slice_5um.lef \
                $DB_LEF_PATH/sky130_ef_io__connect_vcchib_vccd_and_vswitch_vddio_slice_20um.lef \
                $DB_LEF_PATH/sky130_ef_io__corner_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__disconnect_vccd_slice_5um.lef \
                $DB_LEF_PATH/sky130_ef_io__disconnect_vdda_slice_5um.lef \
                $DB_LEF_PATH/sky130_ef_io__gpiov2_pad_wrapped.lef \
                $DB_LEF_PATH/sky130_ef_io__vccd_hvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vccd_lvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vdda_hvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vdda_lvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vddio_hvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vddio_lvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vssa_hvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vssa_lvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vssd_hvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vssd_lvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vssio_hvc_pad.lef \
                $DB_LEF_PATH/sky130_ef_io__vssio_lvc_pad.lef \
                $DB_LEF_PATH/sky130_fd_io__top_xres4v2.lef \
                $DB_LEF_PATH/sky130io_fill.lef \
                $DB_LEF_PATH/sky130_sram_1rw1r_128x256_8.lef \
                $DB_LEF_PATH/sky130_sram_1rw1r_44x64_8.lef \
                $DB_LEF_PATH/sky130_sram_1rw1r_64x256_8.lef \
                $DB_LEF_PATH/sky130_sram_1rw1r_80x64_8.lef"

    #===========================================================
    ##   lib path
    #===========================================================
    set LIB_PATH "$DB_LIB_PATH/sky130_fd_sc_hd__tt_025C_1v80.lib \
          $DB_LIB_PATH/sky130_dummy_io.lib \
          $DB_LIB_PATH/sky130_sram_1rw1r_128x256_8_TT_1p8V_25C.lib \
          $DB_LIB_PATH/sky130_sram_1rw1r_44x64_8_TT_1p8V_25C.lib \
          $DB_LIB_PATH/sky130_sram_1rw1r_64x256_8_TT_1p8V_25C.lib \
          $DB_LIB_PATH/sky130_sram_1rw1r_80x64_8_TT_1p8V_25C.lib"
}

set LIB_PATH_FIXFANOUT ${LIB_PATH}
set LIB_PATH_DRV ${LIB_PATH}
set LIB_PATH_HOLD ${LIB_PATH}
set LIB_PATH_SETUP ${LIB_PATH}

#===========================================================
##   sdc path
#===========================================================
set SDC_PATH "$::env(SDC_FILE)"

#===========================================================
##   spef path
#===========================================================
if {[info exists ::env(SPEF_FILE)]} {
    set SPEF_PATH $::env(SPEF_FILE)
}
