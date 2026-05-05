# SDC 约束文件 - SERV (serv_synth_wrapper)
# 硅迹开源 (SiliconTrace Open)

set clk_name clk
set clk_port_name clk
set clk_period 10.0

set clk_port [get_ports $clk_port_name]
set input_ports [all_inputs]
set output_ports [all_outputs]

# 时钟定义 - 100MHz
create_clock -name $clk_name -period $clk_period $clk_port

# 时钟不确定性
set_clock_uncertainty -setup 0.5 [get_clocks $clk_name]
set_clock_uncertainty -hold 0.1 [get_clocks $clk_name]

# 异步复位不参与同步时序收敛
set_false_path -from [get_ports i_rst]

# IO 建模
set_input_transition 0.20 $input_ports
set_input_delay 2.50 -clock [get_clocks $clk_name] -max $input_ports
set_input_delay 0.20 -clock [get_clocks $clk_name] -min $input_ports
set_output_delay 2.50 -clock [get_clocks $clk_name] -max $output_ports
set_output_delay 0.20 -clock [get_clocks $clk_name] -min $output_ports
set_load 0.05 -max $output_ports
set_load 0.01 -min $output_ports

# 基本电气约束
set_max_transition 1.20 [current_design]
set_max_capacitance 0.10 [current_design]
set_max_fanout 16 [current_design]
