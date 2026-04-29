# SDC 约束文件 - PicoRV32
# 硅迹开源 (SiliconTrace Open)
# 兼容 iEDA STA 引擎（仅支持基本 SDC 命令）

set clk_name clk
set clk_port_name clk
set clk_period 10.0

set clk_port [get_ports $clk_port_name]

# 时钟定义 - 100MHz
create_clock -name $clk_name -period $clk_period $clk_port

# 时钟不确定性
set_clock_uncertainty 0.5 [get_clocks $clk_name]
