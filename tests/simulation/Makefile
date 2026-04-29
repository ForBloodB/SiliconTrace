# PicoRV32 仿真测试 Makefile
# 硅迹开源 (SiliconTrace Open)

TOPLEVEL = tb_picorv32
RTL_DIR  = ../../rtl/picorv32
SIM_DIR  = .

VVP      = vvp
IVERILOG = iverilog
GTKWAVE  = gtkwave

.PHONY: all sim wave clean

all: sim

# 编译
$(TOPLEVEL).vvp: $(TOPLEVEL).v $(RTL_DIR)/picorv32.v
	$(IVERILOG) -o $@ -s $(TOPLEVEL) $^

# 运行仿真
sim: $(TOPLEVEL).vvp
	$(VVP) $<

# 查看波形
wave: $(TOPLEVEL).vcd
	$(GTKWAVE) $< &

# 清理
clean:
	rm -f *.vvp *.vcd
