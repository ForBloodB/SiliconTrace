# iEDA 静态时序分析脚本 - PicoRV32
# 硅迹开源 (SiliconTrace Open)

# 读取布线结果
read_def ../routing/routing.def

# 读取时序库（路径由 run_full_flow.sh 动态替换）
read_lib __PDK_LIB_PATH__

# 读取时序约束
read_sdc ../synthesis/constraints/picorv32.sdc

# 执行 STA
set timing_report_unconstrained_paths true

# 建立时间分析
report_timing -max_paths 10 -late > sta_setup.rpt

# 保持时间分析
report_timing -max_paths 10 -early > sta_hold.rpt

# 时序摘要
report_timing_summary > sta_summary.rpt

# 功耗分析
report_power > power.rpt

puts "静态时序分析完成"
puts "报告文件："
puts "  - sta_setup.rpt (建立时间)"
puts "  - sta_hold.rpt (保持时间)"
puts "  - sta_summary.rpt (时序摘要)"
puts "  - power.rpt (功耗分析)"
