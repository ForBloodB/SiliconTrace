# iEDA 后端流程教程：从门级网表到 GDSII

> 本教程详细介绍如何使用 iEDA 国产开源数字后端 EDA 平台，将综合后的门级网表实现为可制造的 GDSII 物理版图。

## 目录

- [1. 后端流程概述](#1-后端流程概述)
- [2. 准备输入文件](#2-准备输入文件)
- [3. 布局规划 (Floorplan)](#3-布局规划-floorplan)
- [4. 布局 (Placement)](#4-布局-placement)
- [5. 时钟树综合 (Clock Tree Synthesis)](#5-时钟树综合-clock-tree-synthesis)
- [6. 布线 (Routing)](#6-布线-routing)
- [7. 静态时序分析 (STA)](#7-静态时序分析-sta)
- [8. GDSII 生成](#8-gdsii-生成)
- [9. 设计规则检查 (DRC)](#9-设计规则检查-drc)
- [10. 后端脚本示例](#10-后端脚本示例)

---

## 1. 后端流程概述

数字后端设计流程将综合得到的门级网表转换为可制造的物理版图。整个流程包括以下主要阶段：

```
门级网表 (.v) + 约束 (.sdc)
         │
         ▼
    ┌────────────┐
    │  Floorplan  │  布局规划：确定芯片面积、IO 布局、电源规划
    └────┬───────┘
         │
         ▼
    ┌────────────┐
    │ Placement   │  布局：将标准单元放置到芯片上
    └────┬───────┘
         │
         ▼
    ┌────────────┐
    │  CTS        │  时钟树综合：构建时钟分配网络
    └────┬───────┘
         │
         ▼
    ┌────────────┐
    │  Routing    │  布线：连接所有信号线
    └────┬───────┘
         │
         ▼
    ┌────────────┐
    │  STA        │  静态时序分析：验证时序是否满足
    └────┬───────┘
         │
         ▼
    ┌────────────┐
    │  GDSII      │  生成最终版图文件
    └────────────┘
```

### iEDA 子模块对应关系

| 后端阶段 | iEDA 模块 | 功能 |
|---------|----------|------|
| Floorplan | iFP | 芯片面积、IO、电源规划 |
| Placement | iPL | 全局布局 + 详细布局 |
| CTS | iCTS | 时钟树构建 |
| Routing | iRT | 全局布线 + 详细布线 |
| STA | iSTA | 静态时序分析 |
| GDSII | iStreamOut | 版图输出 |
| DRC | iDRC | 设计规则检查 |

---

## 2. 准备输入文件

### 2.1 输入文件清单

后端流程需要以下输入文件：

| 文件类型 | 文件名 | 说明 | 来源 |
|---------|--------|------|------|
| 门级网表 | `picorv32_gate.v` | 综合后的 Verilog 网表 | Yosys |
| 时序约束 | `picorv32.sdc` | 时序约束文件 | 手动编写 |
| 标准单元 LEF | `sky130_fd_sc_hd.lef` | 标准单元物理信息 | PDK |
| 标准单元 Liberty | `sky130_fd_sc_hd__tt_025C_1v80.lib` | 时序信息 | PDK |
| IO 单元 LEF | `sky130_ef_io__...lef` | IO 单元物理信息 | PDK |
| IO 单元 Liberty | `sky130_ef_io__...lib` | IO 单元时序信息 | PDK |
| 工艺文件 | `sky130A.tech` | 工艺层定义 | PDK |

### 2.2 SDC 约束文件

```tcl
# ============================================
# PicoRV32 后端时序约束
# ============================================

# 时钟定义
create_clock -name clk -period 20.0 [get_ports clk]

# 时钟不确定性
set_clock_uncertainty -setup 1.5 [get_clocks clk]
set_clock_uncertainty -hold 0.5 [get_clocks clk]

# 时钟转换时间
set_clock_transition 0.15 [get_clocks clk]

# 输入延迟
set_input_delay -clock clk -max 5.0 [remove_from_collection [all_inputs] [get_ports clk]]
set_input_delay -clock clk -min 2.0 [remove_from_collection [all_inputs] [get_ports clk]]

# 输出延迟
set_output_delay -clock clk -max 5.0 [all_outputs]
set_output_delay -clock clk -min 2.0 [all_outputs]

# 输入驱动
set_drive 0 [get_ports clk]
set_drive 0.01 [get_ports resetn]
set_drive 0.01 [remove_from_collection [all_inputs] [list clk resetn]]

# 输出负载
set_load 0.05 [all_outputs]

# 最大扇出
set_max_fanout 20 [all_inputs]

# 最大转换时间
set_max_transition 1.5 [current_design]

# 最大电容
set_max_capacitance 0.5 [current_design]

# 伪路径
set_false_path -from [get_ports resetn]

# 多周期路径（如果有）
# set_multicycle_path 2 -setup -from [get_pins ...] -to [get_pins ...]
```

---

## 3. 布局规划 (Floorplan)

### 3.1 概念说明

布局规划是后端设计的第一步，主要确定：

1. **芯片面积**: 核心区域和总体面积
2. **IO 布局**: 输入输出引脚的位置
3. **电源规划**: 电源和地线的布局
4. **宏单元布局**: SRAM 等大模块的位置

### 3.2 iEDA Floorplan 配置

```tcl
# ============================================
# iEDA Floorplan 配置
# ============================================

# 设置设计名称
set DESIGN_NAME "picorv32"

# 设置芯片面积（微米）
# PicoRV32 约 12000 um^2，考虑布线通道，设置 200x200 um
set CORE_WIDTH 200.0
set CORE_HEIGHT 200.0

# 核心区域到边缘的距离
set CORE_MARGIN_LEFT 10.0
set CORE_MARGIN_RIGHT 10.0
set CORE_MARGIN_TOP 10.0
set CORE_MARGIN_BOTTOM 10.0

# IO 单元高度
set IO_HEIGHT 1.0

# 行方向和高度
set ROW_DIRECTION "HORIZONTAL"
set SITE_UNIT "unithd"

# 电源条带配置
set POWER_STRIPE_LAYER "met4"
set POWER_STRIPE_WIDTH 1.6
set POWER_STRIPE_PITCH 20.0
```

### 3.3 电源规划

```
                VDD
    ┌──────────────────────────┐
    │  ┌──────────────────┐   │
    │  │                  │   │
    │  │   Core Area      │   │
    │  │                  │   │
    │  │   VDD  VSS  VDD  │   │
    │  │    │    │    │    │   │
    │  │    ▼    ▼    ▼    │   │
    │  │  ──────────────── │   │
    │  │                  │   │
    │  └──────────────────┘   │
    └──────────────────────────┘
                VSS
```

### 3.4 Floorplan 检查

执行完 Floorplan 后，需要检查：

- 核心区域是否足够容纳所有单元
- IO 单元是否正确放置
- 电源条带是否完整
- 是否存在 DRC 违规

---

## 4. 布局 (Placement)

### 4.1 全局布局 (Global Placement)

全局布局将标准单元大致放置到芯片上，目标是最小化线长和拥塞。

```tcl
# iEDA 全局布局配置
set PL_TARGET_DENSITY 0.7    # 目标密度 70%
set PL_WIRE_LENGTH_COEFF 1.0 # 线长权重
set PL_OVERFLOW_ITERATIONS 50 # 溢出迭代次数
```

### 4.2 详细布局 (Detailed Placement)

详细布局调整全局布局的结果，确保所有单元都在合法位置。

```tcl
# 详细布局约束
set PL_MAX_DISPLACEMENT 50   # 最大位移（微米）
set PL_LEGALIZE true         # 是否合法化
```

### 4.3 布局质量评估

布局完成后，检查以下指标：

| 指标 | 说明 | 目标值 |
|------|------|--------|
| 总线长 (Total Wire Length) | 所有连线的总长度 | 最小化 |
| 溢出率 (Overflow) | 布线资源溢出 | < 1% |
| 密度 (Density) | 单元占用面积比 | 60-80% |
| 时序违例 (Timing Violation) | setup/hold 违例 | 0 |

### 4.4 布局优化

如果布局质量不满足要求，可以调整以下参数：

```tcl
# 增加迭代次数
set PL_MAX_ITERATIONS 500

# 调整密度权重
set PL_DENSITY_PENALTY 1.0e+6

# 启用单元填充
set PL_FILLER_CELL "sky130_fd_sc_hd__fill_*"

# 禁止特定区域
set PL_BLOCKAGE_REGIONS { {10 10 50 50} }
```

---

## 5. 时钟树综合 (Clock Tree Synthesis)

### 5.1 概念说明

时钟树综合的目标是构建一个平衡的时钟分配网络，使时钟信号能够同时到达所有触发器。

```
           CLK (源)
            │
        ┌───┴───┐
        │ Buffer │
        └───┬───┘
       ┌────┴────┐
       │         │
   ┌───┴───┐ ┌───┴───┐
   │Buffer │ │Buffer │
   └───┬───┘ └───┬───┘
   ┌───┴───┐ ┌───┴───┐
   │       │ │       │
   FF1    FF2 FF3    FF4
```

### 5.2 CTS 配置

```tcl
# iEDA CTS 配置

# 时钟源
set CTS_CLOCK_PIN "clk"

# 时钟缓冲器单元
set CTS_BUFFER_CELL "sky130_fd_sc_hd__clkbuf_4"

# 时钟树最大延迟
set CTS_MAX_DELAY 2.0    # 纳秒

# 时钟树最大偏差 (skew)
set CTS_MAX_SKEW 0.5     # 纳秒

# 最大扇出
set CTS_MAX_FANOUT 20

# 最大转换时间
set CTS_MAX_TRANSITION 0.3  # 纳秒

# 叶子单元（触发器）
set CTS_SINK_PIN_PATTERN "sky130_fd_sc_hd__dfxtp_*/CLK"

# 时钟树布线层
set CTS_ROUTING_LAYER "met3"
```

### 5.3 CTS 质量评估

CTS 完成后，检查以下指标：

| 指标 | 说明 | 目标值 |
|------|------|--------|
| Skew | 时钟偏差 | < 500ps |
| Max Latency | 最大延迟 | < 2ns |
| Insertion Delay | 插入延迟 | 设计相关 |
| Buffer Count | 缓冲器数量 | 尽量少 |
| Power | 时钟树功耗 | 尽量低 |

### 5.4 CTS 优化

```tcl
# 使用不同驱动强度的缓冲器
set CTS_BUFFER_CELLS {
    "sky130_fd_sc_hd__clkbuf_1"
    "sky130_fd_sc_hd__clkbuf_2"
    "sky130_fd_sc_hd__clkbuf_4"
    "sky130_fd_sc_hd__clkbuf_8"
    "sky130_fd_sc_hd__clkbuf_16"
}

# 启用时钟树平衡
set CTS_ENABLE_BALANCING true

# 设置平衡目标
set CTS_TARGET_SKEW 0.2  # 纳秒
```

---

## 6. 布线 (Routing)

### 6.1 全局布线 (Global Routing)

全局布线将芯片划分为网格，确定每条信号线经过哪些网格。

```tcl
# iEDA 全局布线配置
set RT_GRID_SIZE 10.0     # 网格大小（微米）
set RT_LAYER_PITCH {0.46 0.46 0.46 0.92 0.92 1.84}  # 各层间距

# 布线层分配
# met1: 信号线（水平）
# met2: 信号线（垂直）
# met3: 信号线（水平）
# met4: 电源条带 + 信号线
# met5: 电源条带
```

### 6.2 详细布线 (Detailed Routing)

详细布线在全局布线的基础上，确定每条线的具体走线路径。

```tcl
# 详细布线配置
set RT_DRC_ITERATIONS 10     # DRC 迭代次数
set RT_ALLOW_CONGESTION false # 是否允许拥塞
set RT_OVERFLOW_ITERATIONS 50 # 溢出迭代次数
```

### 6.3 布线层说明

SKY130 工艺的金属层：

| 层名 | 编号 | 方向 | 间距 | 用途 |
|------|------|------|------|------|
| li1 | 0 | - | 0.17 | 本地互连 |
| met1 | 1 | H | 0.46 | 信号线 |
| met2 | 2 | V | 0.46 | 信号线 |
| met3 | 3 | H | 0.46 | 信号线 |
| met4 | 4 | V | 0.92 | 电源/信号 |
| met5 | 5 | H | 1.84 | 电源 |

### 6.4 布线 DRC 规则

```tcl
# 最小宽度
set RT_MIN_WIDTH {
    li1  0.17
    met1 0.14
    met2 0.14
    met3 0.14
    met4 0.30
    met5 0.60
}

# 最小间距
set RT_MIN_SPACING {
    li1  0.17
    met1 0.14
    met2 0.14
    met3 0.14
    met4 0.30
    met5 0.60
}

# 最小面积
set RT_MIN_AREA {
    met1 0.083
    met2 0.083
    met3 0.083
    met4 0.240
    met5 1.200
}
```

### 6.5 布线质量评估

| 指标 | 说明 | 目标值 |
|------|------|--------|
| DRC 违规 | 设计规则违规数 | 0 |
| 溢出 | 布线资源溢出 | 0 |
| 总线长 | 所有连线总长 | 最小化 |
| 通孔数 | Via 数量 | 最小化 |

---

## 7. 静态时序分析 (STA)

### 7.1 概念说明

静态时序分析（STA）验证设计是否满足时序要求，包括：

- **Setup 时间**: 数据必须在时钟沿之前稳定的时间
- **Hold 时间**: 数据必须在时钟沿之后保持的时间

### 7.2 iSTA 配置

```tcl
# iEDA STA 配置

# 读取网表
read_verilog results/placement/picorv32_placed.v

# 读取时序库
read_liberty -max $SC_LIBERTY_SS    ;# Slow corner (setup)
read_liberty -min $SC_LIBERTY_FF    # Fast corner (hold)

# 读取 SDC 约束
read_sdc constraints.sdc

# 读取寄生参数（如果可用）
# read_spef results/routing/picorv32.spef
```

### 7.3 时序报告

```tcl
# 生成时序报告
report_timing -max_paths 10 -nworst 5

# 检查 setup 违例
report_timing -setup

# 检查 hold 违例
report_timing -hold

# 关键路径分析
report_timing -to [get_pins */D] -max_paths 100
```

### 7.4 典型时序报告解读

```
Startpoint: reg_file[0]/CLK (rising edge-triggered flip-flop)
Endpoint: alu_result_reg[31]/D (rising edge-triggered flip-flop)
Path Group: clk
Path Type: max

Fanout     Delay    Time   Description
------------------------------------------------------------
                  0.00   0.00   clock clk (rise edge)
                  0.00   0.00   clock network delay (ideal)
                  0.00   0.00   reg_file[0]/CLK (sky130_fd_sc_hd__dfxtp_1)
         2    0.35   0.35   reg_file[0]/Q (sky130_fd_sc_hd__dfxtp_1)
         1    0.12   0.47   alu_inst/A (sky130_fd_sc_hd__and2_1)
         3    0.28   0.75   alu_inst/X (sky130_fd_sc_hd__and2_1)
         ...
                        18.50   data arrival time

                 20.00   20.00   clock clk (rise edge)
                  0.00   20.00   clock network delay (ideal)
                 -0.50   19.50   library setup time
                        19.50   data required time
------------------------------------------------------------
                        19.50   data required time
                       -18.50   data arrival time
------------------------------------------------------------
                         1.00   slack (MET)
```

### 7.5 时序违例修复

如果存在时序违例，可以采用以下方法：

1. **调整布局**: 使用时序驱动的布局
2. **插入缓冲器**: 在关键路径上插入缓冲器
3. **调整单元大小**: 使用更大驱动能力的单元
4. **优化逻辑**: 重新综合关键路径

---

## 8. GDSII 生成

### 8.1 GDSII 格式说明

GDSII 是集成电路版图的标准文件格式，包含所有物理层的几何信息。

### 8.2 iStreamOut 配置

```tcl
# iEDA GDSII 输出配置

# 设置输出文件
set GDS_OUTPUT_FILE "results/gds/picorv32.gds"

# 设置顶层单元名
set TOP_CELL_NAME "picorv32"

# 设置 GDSII 精度
set GDS_UNIT 0.001    # 微米

# 设置层映射
set GDS_LAYER_MAP {
    {1   "nwelldrawing"}
    {5   "pdiffusiondrawing"}
    {6   "ndiffusiondrawing"}
    {16  "nplusdrawing"}
    {17  "pplusdrawing"}
    {18  "polydrawing"}
    {20  "contactdrawing"}
    {21  "met1drawing"}
    {22  "via1drawing"}
    {23  "met2drawing"}
    {24  "via2drawing"}
    {25  "met3drawing"}
    {26  "via3drawing"}
    {27  "met4drawing"}
    {28  "via4drawing"}
    {29  "met5drawing"}
    {44  "labeldrawing"}
    {46  "pindrawing"}
    {48  "textdrawing"}
}
```

### 8.3 生成 GDSII

```tcl
# 执行 GDSII 输出
write_gds -output $GDS_OUTPUT_FILE \
          -top_cell $TOP_CELL_NAME \
          -unit $GDS_UNIT
```

### 8.4 GDSII 查看

使用 KLayout 查看生成的 GDSII：

```bash
# 安装 KLayout
sudo apt install -y klayout

# 打开 GDSII 文件
klayout results/gds/picorv32.gds
```

---

## 9. 设计规则检查 (DRC)

### 9.1 DRC 概念

DRC（Design Rule Check）验证版图是否满足工艺制造规则。

### 9.2 iDRC 配置

```tcl
# iEDA DRC 配置

# 设置 DRC 规则文件
set DRC_RULE_FILE "$PDK_PATH/libs.tech/klayout/drc/sky130A.lydrc"

# 执行 DRC
run_drc -input results/gds/picorv32.gds \
        -rules $DRC_RULE_FILE \
        -output results/drc/picorv32.drc
```

### 9.3 常见 DRC 违规

| 违规类型 | 说明 | 解决方法 |
|---------|------|---------|
| 最小宽度 | 金属线太窄 | 增加线宽 |
| 最小间距 | 两条线太近 | 增加间距 |
| 最小面积 | 金属面积太小 | 增大面积 |
| 通孔覆盖 | Via 未被金属完全覆盖 | 调整 Via 大小 |
| 密度违规 | 金属密度不满足要求 | 添加金属填充 |

---

## 10. 后端脚本示例

### 10.1 完整的 iEDA 后端脚本

```tcl
#!/usr/bin/env ieda
# ============================================
# SiliconTrace Open - iEDA 后端流程脚本
# 目标: PicoRV32 RISC-V 核心
# 工艺: SKY130 130nm
# ============================================

# 设置变量
set DESIGN "picorv32"
set TOP_MODULE "picorv32"
set RESULTS_DIR "../results"
set PDK_PATH $::env(PDK_PATH)
set SC_LIBERTY $::env(SC_LIBERTY)
set SC_LEF $::env(SC_LEF)

# 创建输出目录
file mkdir $RESULTS_DIR/floorplan
file mkdir $RESULTS_DIR/placement
file mkdir $RESULTS_DIR/cts
file mkdir $RESULTS_DIR/routing
file mkdir $RESULTS_DIR/sta
file mkdir $RESULTS_DIR/gds

# ============================================
# 1. 读取输入文件
# ============================================
puts "=== 读取输入文件 ==="
read_verilog ../synth/results/synth/${DESIGN}_gate.v
read_liberty -lib $SC_LIBERTY
read_lef $SC_LEF
read_sdc ../synth/constraints.sdc

# ============================================
# 2. Floorplan
# ============================================
puts "=== 执行 Floorplan ==="
init_floorplan \
    -core_area {0 0 200 200} \
    -core_site unithd \
    -io_site unithdd

# 添加电源条带
add_power_stripe \
    -layer met4 \
    -width 1.6 \
    -pitch 20 \
    -offset 10

# 验证 Floorplan
check_floorplan

# 保存结果
write_def $RESULTS_DIR/floorplan/${DESIGN}_floorplan.def
puts "Floorplan 完成"

# ============================================
# 3. Placement
# ============================================
puts "=== 执行布局 ==="

# 全局布局
global_placement \
    -density 0.7 \
    -wirelength_coeff 1.0 \
    -max_iterations 500

# 详细布局
detailed_placement \
    -max_displacement 50

# 布局优化
optimize_placement \
    -timing \
    -area

# 检查布局
check_placement

# 保存结果
write_def $RESULTS_DIR/placement/${DESIGN}_placed.def
write_verilog $RESULTS_DIR/placement/${DESIGN}_placed.v
puts "布局完成"

# ============================================
# 4. Clock Tree Synthesis
# ============================================
puts "=== 执行时钟树综合 ==="

# 配置 CTS
set_clock_tree_config \
    -buffer_cell "sky130_fd_sc_hd__clkbuf_4" \
    -max_skew 0.5 \
    -max_delay 2.0 \
    -max_fanout 20

# 执行 CTS
clock_tree_synthesis

# CTS 后优化
optimize_clock_tree

# 检查时钟树
check_clock_tree

# 保存结果
write_def $RESULTS_DIR/cts/${DESIGN}_cts.def
puts "时钟树综合完成"

# ============================================
# 5. Routing
# ============================================
puts "=== 执行布线 ==="

# 全局布线
global_route \
    -grid_size 10 \
    -overflow_iterations 50

# 详细布线
detailed_route \
    -drc_iterations 10

# 布线后优化
optimize_routing

# 检查布线
check_routing

# 保存结果
write_def $RESULTS_DIR/routing/${DESIGN}_routed.def
puts "布线完成"

# ============================================
# 6. STA
# ============================================
puts "=== 执行静态时序分析 ==="

# 更新寄生参数
# extract_parasitics

# 执行 STA
report_timing -max_paths 10

# 检查违例
check_timing

# 保存报告
report_timing > $RESULTS_DIR/sta/timing_report.txt
report_power > $RESULTS_DIR/sta/power_report.txt
puts "静态时序分析完成"

# ============================================
# 7. GDSII 输出
# ============================================
puts "=== 生成 GDSII ==="

write_gds \
    -output $RESULTS_DIR/gds/${DESIGN}.gds \
    -top_cell $DESIGN

puts "GDSII 生成完成"

# ============================================
# 8. DRC
# ============================================
puts "=== 执行 DRC ==="

# 注: DRC 需要 KLayout 或专用工具
# run_drc -input $RESULTS_DIR/gds/${DESIGN}.gds

puts "后端流程全部完成！"
puts "结果保存在 $RESULTS_DIR/ 目录下"
```

### 10.2 运行后端流程

```bash
# 确保环境变量已加载
source ~/.eda_env

# 进入后端目录
cd $SILICONTRACE_ROOT/backend

# 运行 iEDA
ieda -script backend_flow.tcl 2>&1 | tee results/backend.log
```

### 10.3 后端流程 Makefile

```makefile
# Makefile for iEDA backend flow

# 环境变量
PDK_PATH ?= $(HOME)/pdk/sky130A
SC_LIBERTY ?= $(PDK_PATH)/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
SC_LEF ?= $(PDK_PATH)/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
DESIGN ?= picorv32
RESULTS_DIR ?= results

.PHONY: all floorplan placement cts routing sta gds clean

all: gds

floorplan: $(RESULTS_DIR)/floorplan/$(DESIGN)_floorplan.def

$(RESULTS_DIR)/floorplan/$(DESIGN)_floorplan.def:
	@mkdir -p $(RESULTS_DIR)/floorplan
	ieda -script scripts/floorplan.tcl 2>&1 | tee $(RESULTS_DIR)/floorplan/floorplan.log

placement: floorplan $(RESULTS_DIR)/placement/$(DESIGN)_placed.def

$(RESULTS_DIR)/placement/$(DESIGN)_placed.def:
	@mkdir -p $(RESULTS_DIR)/placement
	ieda -script scripts/placement.tcl 2>&1 | tee $(RESULTS_DIR)/placement/placement.log

cts: placement $(RESULTS_DIR)/cts/$(DESIGN)_cts.def

$(RESULTS_DIR)/cts/$(DESIGN)_cts.def:
	@mkdir -p $(RESULTS_DIR)/cts
	ieda -script scripts/cts.tcl 2>&1 | tee $(RESULTS_DIR)/cts/cts.log

routing: cts $(RESULTS_DIR)/routing/$(DESIGN)_routed.def

$(RESULTS_DIR)/routing/$(DESIGN)_routed.def:
	@mkdir -p $(RESULTS_DIR)/routing
	ieda -script scripts/routing.tcl 2>&1 | tee $(RESULTS_DIR)/routing/routing.log

sta: routing
	@mkdir -p $(RESULTS_DIR)/sta
	ieda -script scripts/sta.tcl 2>&1 | tee $(RESULTS_DIR)/sta/sta.log

gds: sta $(RESULTS_DIR)/gds/$(DESIGN).gds

$(RESULTS_DIR)/gds/$(DESIGN).gds:
	@mkdir -p $(RESULTS_DIR)/gds
	ieda -script scripts/gds.tcl 2>&1 | tee $(RESULTS_DIR)/gds/gds.log

clean:
	rm -rf $(RESULTS_DIR)/*
```

---

## 总结

通过本教程，你已经学会了 iEDA 后端流程的各个阶段：

1. **Floorplan**: 确定芯片面积和电源规划
2. **Placement**: 将标准单元放置到芯片上
3. **CTS**: 构建时钟树网络
4. **Routing**: 连接所有信号线
5. **STA**: 验证时序是否满足
6. **GDSII**: 生成最终版图文件
7. **DRC**: 检查设计规则

> **下一步**: 完成后端流程后，请继续阅读 [04_kicad_testboard.md](./04_kicad_testboard.md) 学习如何设计测试 PCB 板。
