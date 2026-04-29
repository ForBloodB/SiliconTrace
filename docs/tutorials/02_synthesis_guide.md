# Yosys 综合教程：从 Verilog RTL 到门级网表

> 本教程详细介绍如何使用 Yosys 开源综合工具将 PicoRV32 RISC-V 处理器的 RTL 代码综合为面向 SKY130 工艺的门级网表。

## 目录

- [1. PicoRV32 RTL 概述](#1-picorv32-rtl-概述)
- [2. SKY130 标准单元库介绍](#2-sky130-标准单元库介绍)
- [3. 编写综合脚本](#3-编写综合脚本)
- [4. 执行综合](#4-执行综合)
- [5. 理解综合结果](#5-理解综合结果)
- [6. 常见错误与解决方案](#6-常见错误与解决方案)
- [7. 综合优化技巧](#7-综合优化技巧)

---

## 1. PicoRV32 RTL 概述

PicoRV32 是一个面积优化的 RISC-V（RV32IMC）处理器核心，由 Claire Wolf 设计。它是开源 RISC-V 生态中最流行的轻量级核心之一。

### 1.1 核心特性

| 特性 | 说明 |
|------|------|
| 指令集 | RV32I + 部分 M 扩展（乘除法）+ C 扩展（压缩指令） |
| 流水线 | 非流水线，每条指令 3-4 个周期 |
| 总线接口 | 自定义 LOOKUP 接口 / AXI4-Lite / Wishbone |
| 面积 | 约 4800 门（仅 RV32I） |
| 频率 | SKY130 工艺下可达 100MHz+ |

### 1.2 关键 RTL 文件

```
picorv32/
├── picorv32.v          # 主核心模块
├── picorv32_axi.v      # AXI4-Lite 接口包装
├── picorv32_wb.v       # Wishbone 接口包装
└── testbench.v         # 仿真测试平台
```

### 1.3 核心模块接口

```verilog
module picorv32 #(
    parameter [0:0] ENABLE_COUNTERS = 1,
    parameter [0:0] ENABLE_COUNTERS64 = 1,
    parameter [0:0] ENABLE_REGS_16_31 = 1,
    parameter [0:0] ENABLE_REGS_DUALPORT = 1,
    parameter [0:0] LATCHED_MEM_RDATA = 0,
    parameter [0:0] TWO_STAGE_SHIFT = 1,
    parameter [0:0] BARREL_SHIFTER = 0,
    parameter [0:0] TWO_CYCLE_COMPARE = 0,
    parameter [0:0] TWO_CYCLE_ALU = 0,
    parameter [0:0] COMPRESSED_ISA = 1,
    parameter [0:0] CATCH_MISALIGN = 1,
    parameter [0:0] CATCH_ILLINSN = 1,
    parameter [0:0] ENABLE_PCPI = 0,
    parameter [0:0] ENABLE_MUL = 1,
    parameter [0:0] ENABLE_DIV = 1,
    parameter [0:0] ENABLE_IRQ = 1,
    parameter [0:0] ENABLE_IRQ_QREGS = 1,
    parameter [0:0] ENABLE_IRQ_TIMER = 1,
    parameter [0:0] ENABLE_TRACE = 0,
    parameter [0:0] REGS_INIT_ZERO = 0,
    parameter [31:0] MASKED_IRQ = 32'h 0000_0000,
    parameter [31:0] LATCHED_IRQ = 32'h ffff_ffff,
    parameter [31:0] PROGADDR_RESET = 32'h 0000_0000,
    parameter [31:0] PROGADDR_IRQ = 32'h 0000_0010,
    parameter [31:0] STACKADDR = 32'h ffff_ffff
) (
    input             clk,
    input             resetn,
    output            trap,

    // 内存接口
    output            mem_valid,
    output [31:0]     mem_addr,
    output [31:0]     mem_wdata,
    output [ 3:0]     mem_wstrb,
    input             mem_ready,
    input  [31:0]     mem_rdata,

    // ... 其他接口省略
);
```

### 1.4 综合参数选择

对于 SiliconTrace 项目，我们选择以下配置：

```verilog
// 推荐的综合配置
ENABLE_COUNTERS     = 1    // 启用性能计数器
ENABLE_COUNTERS64   = 1    // 启用 64 位计数器
ENABLE_REGS_16_31   = 1    // 启用 x16-x31 寄存器
COMPRESSED_ISA      = 1    // 启用 RV32C 压缩指令
CATCH_MISALIGN      = 1    // 捕获未对齐访问
CATCH_ILLINSN       = 1    // 捕获非法指令
ENABLE_MUL          = 1    // 启用乘法器
ENABLE_DIV          = 1    // 启用除法器
ENABLE_IRQ          = 1    // 启用中断
BARREL_SHIFTER      = 0    // 不使用桶形移位器（节省面积）
TWO_STAGE_SHIFT     = 1    // 两级移位器
```

---

## 2. SKY130 标准单元库介绍

### 2.1 库目录结构

```
$PDK_PATH/libs.ref/sky130_fd_sc_hd/
├── lib/                    # Liberty 时序库 (.lib)
│   ├── sky130_fd_sc_hd__tt_025C_1v80.lib    # 典型 corner
│   ├── sky130_fd_sc_hd__ff_n40C_1v95.lib    # Fast corner
│   ├── sky130_fd_sc_hd__ss_100C_1v60.lib    # Slow corner
│   └── ...
├── lef/                    # LEF 物理库 (.lef)
│   ├── sky130_fd_sc_hd.lef                  # 抽象 LEF
│   └── sky130_fd_sc_hd__full.lef            # 完整 LEF
├── verilog/                # Verilog 行为模型
│   ├── primitives.v                         # 基础原语
│   └── sky130_fd_sc_hd.v                    # 标准单元
└── spice/                  # SPICE 网表
```

### 2.2 Liberty 文件解读

Liberty (.lib) 文件描述了标准单元的时序、功耗和面积信息。以下是关键字段的解读：

```
cell ("sky130_fd_sc_hd__and2_1") {
    area : 3.072;                    # 单元面积（平方微米）
    cell_leakage_power : 0.0042;    # 静态功耗（微瓦）

    pin ("A") {
        direction : input;
        capacitance : 0.007650;     # 输入电容（皮法）
    }

    pin ("B") {
        direction : input;
        capacitance : 0.007650;
    }

    pin ("X") {
        direction : output;
        function : "A&B";           # 逻辑功能
        timing () {
            related_pin : "A";
            cell_rise (delay_template_7x7) { ... }  # 上升延迟
            cell_fall (delay_template_7x7) { ... }  # 下降延迟
        }
    }
}
```

### 2.3 常用标准单元

| 单元名称 | 功能 | 说明 |
|---------|------|------|
| `sky130_fd_sc_hd__inv_*` | 反相器 | 驱动能力从 1 到 16 |
| `sky130_fd_sc_hd__and2_*` | 2 输入与门 | 多种驱动强度 |
| `sky130_fd_sc_hd__or2_*` | 2 输入或门 | 多种驱动强度 |
| `sky130_fd_sc_hd__nand2_*` | 2 输入与非门 | 基础逻辑门 |
| `sky130_fd_sc_hd__nor2_*` | 2 输入或非门 | 基础逻辑门 |
| `sky130_fd_sc_hd__mux2_*` | 2 选 1 多路选择器 | 数据选择 |
| `sky130_fd_sc_hd__dfxtp_*` | D 触发器（正沿） | 带复位 |
| `sky130_fd_sc_hd__dfrtp_*` | D 触发器（带复位） | 同步复位 |
| `sky130_fd_sc_hd__clkbuf_*` | 时钟缓冲器 | 时钟树用 |
| `sky130_fd_sc_hd__buf_*` | 缓冲器 | 信号缓冲 |

### 2.4 HD vs HS 库选择

| 特性 | sky130_fd_sc_hd | sky130_fd_sc_hs |
|------|-----------------|-----------------|
| 全称 | High Density | High Speed |
| 面积 | 小 | 大 |
| 速度 | 较慢 | 较快 |
| 功耗 | 较低 | 较高 |
| 适用场景 | 面积优先设计 | 速度优先设计 |
| 本项目 | **推荐使用** | 备选 |

---

## 3. 编写综合脚本

### 3.1 项目目录结构

```
SiliconTrace_Open/
├── rtl/
│   └── picorv32/
│       └── picorv32.v
├── synth/
│   ├── synth.ys            # Yosys 综合脚本
│   ├── synth.ys.tcl        # TCL 版综合脚本（可选）
│   └── constraints.sdc     # 时序约束文件
└── results/
    └── synth/
        ├── picorv32_gate.v     # 综合后的门级网表
        ├── picorv32_gate.sdf   # 时序信息
        └── synth_stat.txt      # 综合报告
```

### 3.2 Yosys 综合脚本 (synth.ys)

以下是完整的综合脚本：

```tcl
# ============================================
# SiliconTrace Open - Yosys 综合脚本
# 目标: PicoRV32 RISC-V 核心
# 工艺: SKY130 130nm
# ============================================

# ---- 1. 读取 RTL 源码 ----
read_verilog -DENABLE_COUNTERS=1 \
             -DENABLE_COUNTERS64=1 \
             -DENABLE_REGS_16_31=1 \
             -DENABLE_REGS_DUALPORT=1 \
             -DCOMPRESSED_ISA=1 \
             -DCATCH_MISALIGN=1 \
             -DCATCH_ILLINSN=1 \
             -DENABLE_MUL=1 \
             -DENABLE_DIV=1 \
             -DENABLE_IRQ=1 \
             -DENABLE_IRQ_QREGS=1 \
             -DENABLE_IRQ_TIMER=1 \
             -DTWO_STAGE_SHIFT=1 \
             -DBARREL_SHIFTER=0 \
             -DSTACKADDR=32'hffffffff \
             -DPROGADDR_RESET=32'h00000000 \
             -DPROGADDR_IRQ=32'h00000010 \
             rtl/picorv32/picorv32.v

# ---- 2. 设计层次化检查 ----
hierarchy -top picorv32 -check

# ---- 3. 顶层模块优化 ----
proc
flatten
opt_clean

# ---- 4. 逻辑优化 ----
opt -full
techmap
opt -full

# ---- 5. 映射到 SKY130 标准单元库 ----
# 读取标准单元库
read_liberty -lib $::env(SC_LIBERTY)

# 使用 ABC 进行逻辑映射
abc -liberty $::env(SC_LIBERTY) \
    -script +strash;scorr;ifraig;retime,{D};strash;dch,-f;map,-M,1,{(C+D)};

# ---- 6. 后映射优化 ----
opt_clean
opt -fast

# ---- 7. 时钟树缓冲插入 ----
# 注意: Yosys 综合阶段不插入时钟树，由 iEDA CTS 完成
# 这里只做基本的时钟缓冲映射
techmap -map +/sky130_fd_sc_hd/cells_map.v

# ---- 8. 输出结果 ----
# 写入门级 Verilog 网表
write_verilog -noattr -noexpr -nohex -nodec \
    results/synth/picorv32_gate.v

# 写入 BLIF 格式（供后续工具使用）
write_blif -param -attr -cname \
    results/synth/picorv32_gate.blif

# 写入 JSON 格式（供 iEDA 使用）
write_json results/synth/picorv32_gate.json

# ---- 9. 生成报告 ----
stat -liberty $::env(SC_LIBERTY) > results/synth/synth_stat.txt
tee -o results/synth/check.txt check
```

### 3.3 时序约束文件 (constraints.sdc)

```tcl
# ============================================
# SDC 时序约束
# 目标时钟频率: 50 MHz (周期 20ns)
# ============================================

# 时钟定义
create_clock -name clk -period 20.0 [get_ports clk]

# 时钟不确定性（skew + jitter）
set_clock_uncertainty 1.0 [get_clocks clk]

# 输入延迟（相对于时钟）
set_input_delay -clock clk -max 5.0 [remove_from_collection [all_inputs] [get_ports clk]]
set_input_delay -clock clk -min 1.0 [remove_from_collection [all_inputs] [get_ports clk]]

# 输出延迟
set_output_delay -clock clk -max 5.0 [all_outputs]
set_output_delay -clock clk -min 1.0 [all_outputs]

# 输入驱动
set_drive 0 [get_ports clk]
set_drive 1 [remove_from_collection [all_inputs] [get_ports clk]]

# 输出负载
set_load 0.1 [all_outputs]

# 伪路径（如果存在）
# set_false_path -from [get_ports resetn]
```

### 3.4 TCL 版综合脚本 (synth.tcl)

如果需要更灵活的控制，可以使用 TCL 脚本：

```tcl
#!/usr/bin/env yosys -s
# ============================================
# SiliconTrace Open - TCL 综合脚本
# ============================================

# 设置变量
set DESIGN "picorv32"
set TOP_MODULE "picorv32"
set RTL_DIR "../rtl/picorv32"
set RESULT_DIR "../results/synth"
set PDK_PATH $::env(PDK_PATH)
set SC_LIBERTY $::env(SC_LIBERTY)

# 创建输出目录
file mkdir $RESULT_DIR

# 读取 RTL
yosys read_verilog -DENABLE_MUL=1 -DENABLE_DIV=1 $RTL_DIR/picorv32.v

# 设置顶层
yosys hierarchy -top $TOP_MODULE

# 综合流程
yosys proc
yosys flatten
yosys opt -full
yosys techmap
yosys opt -full

# 读取标准单元库
yosys read_liberty -lib $SC_LIBERTY

# ABC 逻辑映射
yosys abc -liberty $SC_LIBERTY

# 后优化
yosys opt_clean

# 输出
yosys write_verilog -noattr $RESULT_DIR/${DESIGN}_gate.v
yosys stat -liberty $SC_LIBERTY

puts "综合完成！结果保存在 $RESULT_DIR/"
```

---

## 4. 执行综合

### 4.1 准备工作

```bash
# 确保环境变量已加载
source ~/.eda_env

# 进入综合目录
cd $SILICONTRACE_ROOT/synth

# 创建输出目录
mkdir -p results/synth
```

### 4.2 运行综合

```bash
# 使用 Yosys 执行综合脚本
yosys synth.ys 2>&1 | tee results/synth/synth.log
```

### 4.3 使用 Makefile

为了方便重复执行，可以创建 Makefile：

```makefile
# Makefile for Yosys synthesis

# 环境变量
PDK_PATH ?= $(HOME)/pdk/sky130A
SC_LIBERTY ?= $(PDK_PATH)/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
DESIGN ?= picorv32
RTL_DIR ?= ../rtl/picorv32
RESULT_DIR ?= results/synth

.PHONY: all clean synth

all: synth

synth: $(RESULT_DIR)/$(DESIGN)_gate.v

$(RESULT_DIR)/$(DESIGN)_gate.v: $(RTL_DIR)/picorv32.v synth.ys
	@mkdir -p $(RESULT_DIR)
	yosys \
		-p "read_verilog -DENABLE_MUL=1 -DENABLE_DIV=1 $(RTL_DIR)/picorv32.v" \
		-p "hierarchy -top $(DESIGN)" \
		-p "proc; flatten; opt -full; techmap; opt -full" \
		-p "read_liberty -lib $(SC_LIBERTY)" \
		-p "abc -liberty $(SC_LIBERTY)" \
		-p "opt_clean" \
		-p "write_verilog -noattr $(RESULT_DIR)/$(DESIGN)_gate.v" \
		-p "stat -liberty $(SC_LIBERTY) > $(RESULT_DIR)/synth_stat.txt" \
		2>&1 | tee $(RESULT_DIR)/synth.log

clean:
	rm -rf $(RESULT_DIR)/*
```

运行方式：

```bash
make synth
```

---

## 5. 理解综合结果

### 5.1 综合报告解读

综合完成后，Yosys 会输出统计报告。以下是一个典型的报告示例：

```
=== picorv32 ===

   Number of wires:               4521
   Number of wire bits:           5832
   Number of public wires:         156
   Number of public wire bits:     467
   Number of memories:               0
   Number of memory bits:            0
   Number of processes:              0
   Number of cells:               4892
     sky130_fd_sc_hd__and2_2        89
     sky130_fd_sc_hd__and3_2        34
     sky130_fd_sc_hd__buf_1        156
     sky130_fd_sc_hd__buf_2         78
     sky130_fd_sc_hd__clkbuf_1      12
     sky130_fd_sc_hd__dfxtp_1      287
     sky130_fd_sc_hd__inv_1         95
     sky130_fd_sc_hd__mux2_1       234
     sky130_fd_sc_hd__nand2_1      456
     sky130_fd_sc_hd__nor2_1       312
     sky130_fd_sc_hd__or2_2        167
     sky130_fd_sc_hd__xor2_1        89
     ...

   Area: 12847.56 um^2
   Estimated frequency: 85.2 MHz
```

### 5.2 关键指标说明

| 指标 | 说明 | PicoRV32 典型值 |
|------|------|-----------------|
| Number of cells | 标准单元总数 | ~4800 |
| Number of wires | 连线总数 | ~4500 |
| Area | 总面积 | ~12800 um^2 |
| DFF 触发器数 | 寄存器数量 | ~287 |
| 组合逻辑门 | 与/或/非等 | ~4500 |

### 5.3 面积估算

SKY130 HD 库中各单元的面积：

```
sky130_fd_sc_hd__inv_1:    1.44 um^2
sky130_fd_sc_hd__and2_1:   3.07 um^2
sky130_fd_sc_hd__nand2_1:  2.30 um^2
sky130_fd_sc_hd__nor2_1:   2.30 um^2
sky130_fd_sc_hd__dfxtp_1: 12.96 um^2
```

PicoRV32 的面积估算：
- 组合逻辑: ~3500 cells * 平均 2.5 um^2 = ~8750 um^2
- 时序逻辑: ~287 DFFs * 12.96 um^2 = ~3720 um^2
- 总面积: ~12470 um^2 (约 0.012 mm^2)

---

## 6. 常见错误与解决方案

### 6.1 错误: "Module `xxx` not found"

**原因**: 模块层次化问题，缺少子模块或参数未正确传递。

**解决方案**:
```tcl
# 在 read_verilog 之前确保所有源文件都被读取
read_verilog rtl/picorv32/picorv32.v

# 检查层次结构
hierarchy -top picorv32 -check

# 如果有未解析的模块，手动指定
hierarchy -top picorv32 -libdir rtl/
```

### 6.2 错误: "Unsupported Verilog construct"

**原因**: RTL 代码中使用了 Yosys 不支持的 Verilog 特性。

**解决方案**:
```tcl
# Yosys 不支持的部分特性:
# - generate 语句中的复杂条件
# - 某些 SystemVerilog 特性
# - 部分 Verilog-2001 特性

# 解决方法:
# 1. 检查 Yosys 文档确认支持的特性
# 2. 修改 RTL 代码，使用支持的语法重写
# 3. 使用 read_verilog -defer 解析问题
```

### 6.3 错误: "ABC: cannot read Liberty file"

**原因**: Liberty 文件路径错误或格式问题。

**解决方案**:
```bash
# 检查 Liberty 文件是否存在
ls -la $SC_LIBERTY

# 检查环境变量
echo $SC_LIBERTY

# 使用绝对路径
read_liberty -lib /full/path/to/sky130_fd_sc_hd__tt_025C_1v80.lib
```

### 6.4 错误: "Wire `xxx` has no driver"

**原因**: 存在未驱动的线网，通常是设计错误。

**解决方案**:
```tcl
# 检查设计
check

# 查看未驱动的线网
opt -full

# 如果是故意的（如三态总线），可以忽略
# 或者添加默认驱动
setundef -zero  # 将未定义的信号设为 0
```

### 6.5 警告: "Replacing memory `xxx` with list of registers"

**原因**: Yosys 将存储器替换为寄存器阵列。

**解决方案**:
```tcl
# 如果存储器较大，考虑使用存储器编译器
memory_map

# 或者手动实例化 SRAM
# read_verilog sram_wrapper.v
```

---

## 7. 综合优化技巧

### 7.1 使用 ABC 优化脚本

ABC 是 Yosys 内置的逻辑优化工具，可以通过脚本控制优化策略：

```tcl
# 基本映射
abc -liberty $SC_LIBERTY

# 使用更激进的优化
abc -liberty $SC_LIBERTY \
    -script +strash;scorr;ifraig;retime,{D};strash;dch,-f;map,-M,1,{(C+D)}

# 面积优化
abc -liberty $SC_LIBERTY \
    -script +strash;scorr;ifraig;map,-a,-M,1,{(C+D)}

# 速度优化
abc -liberty $SC_LIBERTY \
    -script +strash;scorr;ifraig;retime,{D};strash;dch,-f;map,-M,0,{(C+D)}
```

### 7.2 时序约束驱动综合

```tcl
# 读取 SDC 约束
read_sdc constraints.sdc

# 或者在脚本中直接指定
# 时钟周期 20ns (50MHz)
dfflibmap -liberty $SC_LIBERTY

# 使用 ABC 进行时序驱动映射
abc -liberty $SC_LIBERTY \
    -constr constraints.sdc \
    -script +strash;scorr;ifraig;retime,{D};strash;dch,-f;map,-M,1,{(C+D)}
```

### 7.3 多角分析

```tcl
# 典型 corner
read_liberty -lib $SC_LIBERTY_TT

# Fast corner
read_liberty -lib $SC_LIBERTY_FF

# Slow corner
read_liberty -lib $SC_LIBERTY_SS

# 使用最差 corner 进行综合
abc -liberty $SC_LIBERTY_SS
```

### 7.4 综合后验证

```bash
# 检查综合后的网表语法
yosys -p "read_verilog results/synth/picorv32_gate.v; stat"

# 等价性检查（需要 sby 工具）
sby -f equiv_check.sby
```

### 7.5 生成综合报告

```bash
# 生成详细报告
yosys synth.ys 2>&1 | tee results/synth/synth_full.log

# 提取关键信息
grep -E "(Number of cells|Area|Estimated)" results/synth/synth_full.log
```

---

## 总结

通过本教程，你已经学会了：

1. PicoRV32 RTL 的结构和关键参数
2. SKY130 标准单元库的组织和使用
3. 编写 Yosys 综合脚本
4. 执行综合并解读结果
5. 常见错误的排查方法

> **下一步**: 综合完成后，请继续阅读 [03_backend_flow.md](./03_backend_flow.md) 学习如何使用 iEDA 进行后端实现。
