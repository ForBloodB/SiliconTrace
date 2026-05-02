# Basic timing constraints for the blinky_counter demo.
set clk_period 10.000

set clk_port [get_ports clk]
set input_ports [all_inputs]
set output_ports [all_outputs]

create_clock -name clk -period $clk_period $clk_port
set_clock_uncertainty -setup 0.100 [get_clocks clk]
set_clock_uncertainty -hold 0.050 [get_clocks clk]

set_false_path -from [get_ports resetn]

set_input_delay 1.000 -clock [get_clocks clk] -max $input_ports
set_input_delay 0.100 -clock [get_clocks clk] -min $input_ports
set_output_delay 1.000 -clock [get_clocks clk] -max $output_ports
set_output_delay 0.100 -clock [get_clocks clk] -min $output_ports

set_input_transition 0.100 $input_ports
set_load 0.030 -max $output_ports
set_load 0.010 -min $output_ports

set_max_transition 0.500 [current_design]
set_max_capacitance 0.200 [current_design]
set_max_fanout 16 [current_design]
