# iEDA 布局脚本 - PicoRV32
# 硅迹开源 (SiliconTrace Open)

# 读取布局规划
read_def ../floorplan/floorplan.def

# 设置布局约束
set_db place_density 0.7
set_db place_global_uniform_density true

# 全局布局
place_global

# 详细布局
place_detail

# 保存结果
write_def placement.def

puts "布局完成"
