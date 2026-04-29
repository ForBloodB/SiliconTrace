# iEDA 布局规划脚本 - PicoRV32
# 硅迹开源 (SiliconTrace Open)

# 初始化数据库
set_db init_netlist_dir ../synthesis/results
set_db init_mmmc_file ../scripts/mmmc.tcl

# 读取网表
read_netlist picorv32_netlist.v

# 读取时序约束
read_sdc ../synthesis/constraints/picorv32.sdc

# 初始化设计
init_design

# 布局规划配置
set die_area {0 0 500 500}
set core_area {10 10 490 490}

# 设置布局规划
set_db floorplan_die_area $die_area
set_db floorplan_core_area $core_area

# 设置电源网络
set_db power_net VDD
set_db ground_net VSS

# 添加电源条带
add_power_stripe -net VDD -width 2 -offset 50 -direction horizontal
add_power_stripe -net VSS -width 2 -offset 50 -direction vertical

# 保存布局规划
write_def floorplan.def

puts "布局规划完成"
