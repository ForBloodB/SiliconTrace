# iEDA 布线脚本 - PicoRV32
# 硅迹开源 (SiliconTrace Open)

# 读取时钟树结果
read_def ../cts/cts.def

# 布线配置
set_db route_global_verbose true
set_db route_antenna_diode_insertion true

# 全局布线
route_global

# 详细布线
route_track
route_detail

# 布线后优化
route_opt

# 保存结果
write_def routing.def

puts "布线完成"
