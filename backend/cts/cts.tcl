# iEDA 时钟树综合脚本 - PicoRV32
# 硅迹开源 (SiliconTrace Open)

# 读取布局结果
read_def ../placement/placement.def

# 时钟树配置
set_db cts_target_skew 0.5
set_db cts_target_insertion_delay 0.1

# 设置时钟缓冲器
set_db cts_buffer_cells [list sky130_fd_sc_hd__buf_2 sky130_fd_sc_hd__buf_4 sky130_fd_sc_hd__buf_8]

# 执行时钟树综合
clock_tree_synthesis

# 保存结果
write_def cts.def

puts "时钟树综合完成"
