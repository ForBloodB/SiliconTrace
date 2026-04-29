# iEDA 集成实践：国产开源数字后端平台的探索与挑战

> 作者: SiliconTrace Open 技术团队
> 日期: 2026-04-30
> 标签: #iEDA #国产EDA #开源 #后端设计 #经验分享

---

在 SiliconTrace Open 项目中，我们选择了 iEDA（中科院计算所开发的国产开源数字后端平台）作为后端实现工具。这篇文章记录了我们在集成 iEDA 过程中遇到的挑战、解决方案和经验教训。

## 什么是 iEDA

### 项目背景

iEDA 是由中科院计算技术研究所主导开发的开源数字集成电路 EDA 后端平台。它的目标是构建一个完整的、可替代商业 EDA 工具的开源解决方案。

```
┌─────────────────────────────────────────────────────────────┐
│                      iEDA 平台架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │   iFP   │  │   iPL   │  │   iCTS  │  │   iRT   │      │
│  │Floorplan│  │Placement│  │   CTS   │  │ Routing │      │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │  iSTA   │  │  iDRC   │  │   iTO   │  │iStreamOut│     │
│  │  STA    │  │   DRC   │  │  Timing │  │  GDSII  │      │
│  │         │  │         │  │   Opt   │  │         │      │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 功能 | 状态 |
|------|------|------|
| iFP | Floorplan（布局规划） | 稳定 |
| iPL | Placement（布局） | 稳定 |
| iCTS | Clock Tree Synthesis（时钟树综合） | 稳定 |
| iRT | Routing（布线） | 稳定 |
| iSTA | Static Timing Analysis（静态时序分析） | 稳定 |
| iDRC | Design Rule Check（设计规则检查） | 开发中 |
| iTO | Timing Optimization（时序优化） | 开发中 |
| iStreamOut | GDSII 输出 | 稳定 |

### 为什么选择 iEDA

1. **国产自主**: 完全由国内团队开发，不受国外技术封锁影响
2. **开源透明**: 代码完全开源，可以学习后端算法实现
3. **社区活跃**: 持续更新，问题响应快
4. **文档完善**: 中文文档齐全，学习曲线相对平缓
5. **教育友好**: 适合高校教学和研究

## 集成挑战

### 挑战一：Yosys 到 iEDA 的网表格式转换

#### 问题描述

Yosys 综合输出的 Verilog 网表格式与 iEDA 期望的输入格式存在差异。

```verilog
// Yosys 输出格式示例
module picorv32 (
    input clk,
    input resetn,
    ...
);
    wire _0000_;
    wire _0001_;
    ...
    sky130_fd_sc_hd__dfxtp_1 _1234_ (
        .CLK(clk),
        .D(_0000_),
        .Q(_0001_)
    );
endmodule

// iEDA 期望的格式
module picorv32 (
    input clk,
    input resetn,
    ...
);
    sky130_fd_sc_hd__dfxtp_1 _1234_ (
        .CLK(clk),
        .D(net_0000),
        .Q(net_0001)
    );
endmodule
```

#### 具体差异

| 方面 | Yosys 输出 | iEDA 期望 |
|------|-----------|----------|
| 线网命名 | `_0000_`, `_0001_` | `net_0000`, `net_0001` |
| 常量线网 | `1'b0`, `1'b1` | `VDD`, `VSS` 或特定命名 |
| 模块实例化 | 自动生成名称 | 需要唯一标识 |
| 属性 | 包含 Yosys 属性 | 需要清理 |

#### 解决方案

编写网表转换脚本：

```python
#!/usr/bin/env python3
"""
convert_netlist.py - 将 Yosys 输出的网表转换为 iEDA 兼容格式
"""

import re
import sys

def convert_netlist(input_file, output_file):
    """转换网表文件"""
    with open(input_file, 'r') as f:
        content = f.read()

    # 1. 清理 Yosys 属性
    content = re.sub(r'\\\S+', lambda m: m.group().replace('\\', '_'), content)

    # 2. 转换线网命名
    def convert_wire_name(match):
        prefix = match.group(1)
        num = match.group(2)
        return f'{prefix}net_{num.zfill(4)}'

    content = re.sub(r'(_)(\d+)(_)', convert_wire_name, content)

    # 3. 处理常量线网
    content = content.replace("1'b0", "VSS")
    content = content.replace("1'b1", "VDD")

    # 4. 确保模块名唯一
    instance_count = {}
    def make_unique_instance(match):
        cell_type = match.group(1)
        instance_name = match.group(2)
        if instance_name in instance_count:
            instance_count[instance_name] += 1
            new_name = f"{instance_name}_{instance_count[instance_name]}"
        else:
            instance_count[instance_name] = 0
            new_name = instance_name
        return f'{cell_type} {new_name}'

    content = re.sub(r'(\w+)\s+(\w+)\s*\(', make_unique_instance, content)

    with open(output_file, 'w') as f:
        f.write(content)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python convert_netlist.py input.v output.v")
        sys.exit(1)
    convert_netlist(sys.argv[1], sys.argv[2])
```

### 挑战二：Verilog 解析器的局限性

#### 问题描述

iEDA 内置的 Verilog 解析器对某些语法支持不完整。

#### 不支持的语法

1. **Generate 语句**:
```verilog
// iEDA 解析器可能不支持
genvar i;
generate
    for (i = 0; i < 8; i = i + 1) begin : gen_loop
        assign out[i] = in[i] & enable;
    end
endgenerate
```

2. **参数化模块**:
```verilog
// 复杂的参数传递可能有问题
module my_module #(
    parameter WIDTH = 8,
    parameter DEPTH = 16
) (
    input [WIDTH-1:0] data_in,
    output [WIDTH-1:0] data_out
);
```

3. **SystemVerilog 特性**:
```verilog
// 不支持
always_comb begin
    unique case (sel)
        2'b00: out = a;
        2'b01: out = b;
        default: out = '0;
    endcase
end
```

#### 解决方案

1. **预处理 RTL**:
```python
def preprocess_rtl(input_file, output_file):
    """预处理 RTL 代码，转换不支持的语法"""
    with open(input_file, 'r') as f:
        lines = f.readlines()

    processed_lines = []
    for line in lines:
        # 转换 SystemVerilog 到 Verilog
        line = line.replace('always_comb', 'always @(*)')
        line = line.replace('always_ff', 'always @(posedge clk)')
        line = line.replace('unique case', 'case')
        line = line.replace("'0", "'b0")

        # 移除不支持的属性
        line = re.sub(r'\(\*.*?\*\)', '', line)

        processed_lines.append(line)

    with open(output_file, 'w') as f:
        f.writelines(processed_lines)
```

2. **手动修改 RTL**:
```verilog
// 将 generate 改为直接实例化
// 原代码
genvar i;
generate
    for (i = 0; i < 8; i = i + 1) begin : gen_loop
        assign out[i] = in[i] & enable;
    end
endgenerate

// 改为
assign out[0] = in[0] & enable;
assign out[1] = in[1] & enable;
assign out[2] = in[2] & enable;
assign out[3] = in[3] & enable;
assign out[4] = in[4] & enable;
assign out[5] = in[5] & enable;
assign out[6] = in[6] & enable;
assign out[7] = in[7] & enable;
```

### 挑战三：单元库兼容性（HD vs HS）

#### 问题描述

SKY130 PDK 提供了多个标准单元库变体，选择不当会导致问题。

| 库名称 | 特点 | 适用场景 |
|--------|------|---------|
| sky130_fd_sc_hd | 高密度，面积小 | 面积优先设计 |
| sky130_fd_sc_hs | 高速，驱动强 | 速度优先设计 |
| sky130_fd_sc_ms | 中速 | 折中方案 |
| sky130_fd_sc_ls | 低速，低功耗 | 低功耗设计 |
| sky130_fd_sc_lp | 超低功耗 | IoT 应用 |

#### 遇到的问题

1. **单元名称不匹配**:
```
Error: Cell 'sky130_fd_sc_hd__and2_1' not found in library
```

2. **引脚名称差异**:
```verilog
// HD 库
.sky130_fd_sc_hd__dfxtp_1 (.CLK(clk), .D(d), .Q(q))

// HS 库
.sky130_fd_sc_hs__dfxtp_1 (.CLK(clk), .D(d), .Q(q))
```

3. **驱动能力差异**:
- HD 库最大驱动: `sky130_fd_sc_hd__buf_16`
- HS 库最大驱动: `sky130_fd_sc_hs__buf_16`
- 驱动能力不同，需要调整设计

#### 解决方案

1. **统一使用 HD 库**:
```tcl
# 在综合和后端流程中统一使用 HD 库
set SC_LIB "sky130_fd_sc_hd"
set SC_LIBERTY "$PDK_PATH/libs.ref/$SC_LIB/lib/${SC_LIB}__tt_025C_1v80.lib"
set SC_LEF "$PDK_PATH/libs.ref/$SC_LIB/lef/${SC_LIB}.lef"
```

2. **单元名称映射**:
```python
def map_cell_names(netlist, from_lib, to_lib):
    """映射单元名称"""
    mapping = {
        'sky130_fd_sc_hd__and2_1': 'sky130_fd_sc_hs__and2_1',
        'sky130_fd_sc_hd__or2_1': 'sky130_fd_sc_hs__or2_1',
        # ... 更多映射
    }
    for old_name, new_name in mapping.items():
        netlist = netlist.replace(old_name, new_name)
    return netlist
```

3. **混合库使用**:
```tcl
# 在后端流程中可以混合使用，但需要谨慎
read_liberty -lib $SC_LIBERTY_HD
read_liberty -lib $SC_LIBERTY_HS

# 使用 HD 库进行布局，HS 库用于关键路径优化
```

### 挑战四：SDC 约束兼容性

#### 问题描述

SDC（Synopsys Design Constraints）文件格式在不同工具间存在差异。

#### Yosys SDC vs iEDA SDC

| 特性 | Yosys SDC | iEDA SDC |
|------|----------|----------|
| 时钟定义 | `create_clock` | `create_clock` |
| 输入延迟 | `set_input_delay` | `set_input_delay` |
| 输出延迟 | `set_output_delay` | `set_output_delay` |
| 伪路径 | `set_false_path` | `set_false_path` |
| 多周期 | `set_multicycle_path` | `set_multicycle_path` |
| 驱动 | `set_drive` | `set_drive` |
| 负载 | `set_load` | `set_load` |
| 获取对象 | `get_ports`, `get_pins` | `get_ports`, `get_pins`, `get_cells` |

#### 遇到的问题

1. **对象获取方式不同**:
```tcl
# Yosys
get_ports clk

# iEDA 可能需要
get_ports "clk"
# 或
get_ports {clk}
```

2. **约束范围差异**:
```tcl
# Yosys 支持
set_clock_uncertainty -setup 1.0 [get_clocks clk]

# iEDA 可能需要分开设置
set_clock_uncertainty -setup 1.0 -clock clk
```

3. **通配符支持**:
```tcl
# Yosys
set_input_delay 5.0 [get_ports "data*"]

# iEDA 可能需要显式列出
set_input_delay 5.0 [get_ports {data[0] data[1] ...}]
```

#### 解决方案

编写约束转换脚本：

```tcl
#!/usr/bin/env tclsh
# convert_sdc.tcl - 转换 SDC 约束文件

proc convert_sdc {input output} {
    set fh_in [open $input r]
    set fh_out [open $w]

    while {[gets $fh_in line] >= 0} {
        # 转换对象获取语法
        set line [regsub -all {get_ports\s+(\w+)} $line {get_ports "\1"}]
        set line [regsub -all {get_clocks\s+(\w+)} $line {get_clocks "\1"}]

        # 转换约束语法
        if {[regexp {set_clock_uncertainty\s+-setup\s+([\d.]+)\s+\[get_clocks\s+(\w+)\]} \
             $line -> value clock]} {
            set line "set_clock_uncertainty -setup $value -clock $clock"
        }

        puts $fh_out $line
    }

    close $fh_in
    close $fh_out
}
```

### 挑战五：LEF/DEF 格式兼容

#### 问题描述

LEF（Library Exchange Format）和 DEF（Design Exchange Format）文件在不同工具间可能存在格式差异。

#### 常见问题

1. **LEF 版本差异**:
```
# LEF 5.3 vs LEF 5.8
VERSION 5.3 ;  # Yosys 默认
VERSION 5.8 ;  # iEDA 期望
```

2. **层定义差异**:
```
# 不同工具对层的命名可能不同
LAYER met1 ;  # 标准命名
LAYER metal1 ;  # 另一种命名
```

3. **单位差异**:
```
# 微米 vs 纳米
UNITS DATABASE MICRONS 1000 ;  # 微米单位
UNITS DATABASE MICRONS 1 ;    # 纳米单位
```

#### 解决方案

```python
def convert_lef(input_file, output_file):
    """转换 LEF 文件格式"""
    with open(input_file, 'r') as f:
        content = f.read()

    # 更新版本
    content = content.replace('VERSION 5.3', 'VERSION 5.8')

    # 更新单位（如果需要）
    content = content.replace(
        'UNITS DATABASE MICRONS 1000',
        'UNITS DATABASE MICRONS 1'
    )

    # 统一层命名
    layer_mapping = {
        'metal1': 'met1',
        'metal2': 'met2',
        'metal3': 'met3',
        'metal4': 'met4',
        'metal5': 'met5',
    }
    for old_name, new_name in layer_mapping.items():
        content = content.replace(old_name, new_name)

    with open(output_file, 'w') as f:
        f.write(content)
```

## 经验教训

### 教训一：提前验证工具链兼容性

在项目初期，应该先用小规模设计验证整个工具链的兼容性，而不是等到大设计完成后才发现问题。

```bash
# 验证流程示例
# 1. 创建简单测试设计
cat > test.v << 'EOF'
module test (input a, b, output y);
    assign y = a & b;
endmodule
EOF

# 2. 运行综合
yosys -p "read_verilog test.v; synth; write_verilog test_gate.v"

# 3. 验证 iEDA 兼容性
ieda -p "read_verilog test_gate.v; check_design"
```

### 教训二：建立标准化的输入输出规范

为每个工具定义清晰的输入输出格式规范，避免格式不匹配。

```yaml
# tool_io_spec.yaml
yosys:
  input:
    format: verilog
    encoding: utf-8
  output:
    format: verilog
    attributes: false
    naming: "net_%04d"

ieda:
  input:
    format: verilog
    netlist: true
    lef: "sky130_fd_sc_hd.lef"
    liberty: "sky130_fd_sc_hd__tt_025C_1v80.lib"
    sdc: "constraints.sdc"
  output:
    format: def
    gdsii: true
```

### 教训三：编写自动化测试

建立自动化测试框架，及时发现集成问题。

```python
#!/usr/bin/env python3
"""
test_integration.py - 集成测试脚本
"""

import subprocess
import os

def run_test(test_name, command, expected):
    """运行测试并验证结果"""
    print(f"Running test: {test_name}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  [PASS] {test_name}")
        return True
    else:
        print(f"  [FAIL] {test_name}")
        print(f"  Error: {result.stderr}")
        return False

def main():
    """主测试函数"""
    tests = [
        ("Yosys 综合", "yosys -p 'read_verilog rtl/picorv32.v; synth'", 0),
        ("网表转换", "python convert_netlist.py input.v output.v", 0),
        ("iEDA Floorplan", "ieda -script scripts/floorplan.tcl", 0),
        ("iEDA Placement", "ieda -script scripts/placement.tcl", 0),
        ("iEDA CTS", "ieda -script scripts/cts.tcl", 0),
        ("iEDA Routing", "ieda -script scripts/routing.tcl", 0),
    ]

    passed = 0
    for test_name, command, expected in tests:
        if run_test(test_name, command, expected):
            passed += 1

    print(f"\nResults: {passed}/{len(tests)} tests passed")

if __name__ == '__main__':
    main()
```

### 教训四：充分利用社区资源

iEDA 社区提供了丰富的文档和示例，遇到问题时应该：

1. **查阅官方文档**: iEDA Wiki
2. **搜索 Issue**: GitHub Issues 中可能有类似问题
3. **提问社区**: 在 GitHub Discussions 中提问
4. **查看示例**: iEDA 提供的示例项目

### 教训五：版本管理很重要

工具和 PDK 的版本管理至关重要：

```bash
# 记录工具版本
yosys -V > versions.txt
ieda --version >> versions.txt
volare --version >> versions.txt

# 锁定 PDK 版本
volare enable --pdk sky130 0.0.0.20240115

# 使用 git submodule 管理依赖
git submodule add https://github.com/OSCC-Project/iEDA.git tools/iEDA
```

## 性能优化经验

### 布局优化

```tcl
# 调整布局参数以获得更好结果
global_placement \
    -density 0.7 \
    -wirelength_coeff 1.5 \
    -max_iterations 1000 \
    -overflow_iterations 100
```

### CTS 优化

```tcl
# 优化时钟树
set_clock_tree_config \
    -buffer_cell "sky130_fd_sc_hd__clkbuf_4" \
    -max_skew 0.3 \
    -max_delay 1.5 \
    -max_fanout 15
```

### 布线优化

```tcl
# 优化布线
detailed_route \
    -drc_iterations 20 \
    -overflow_iterations 100
```

## 总结与展望

### 成果

通过本次集成实践，我们：

1. 成功将 iEDA 集成到 SiliconTrace Open 流程中
2. 解决了多个格式兼容性问题
3. 建立了完整的自动化流程
4. 积累了宝贵的集成经验

### iEDA 的优势

1. **完全开源**: 可以学习和修改
2. **国产自主**: 不受技术封锁影响
3. **社区活跃**: 问题响应快
4. **文档完善**: 中文文档齐全

### 未来改进方向

1. **标准化接口**: 推动 iEDA 与主流工具的接口标准化
2. **自动化工具**: 开发更多自动化转换工具
3. **测试覆盖**: 建立更完善的测试体系
4. **性能优化**: 持续优化后端流程性能

### 给后来者的建议

1. **从简单开始**: 先用小设计验证流程
2. **仔细阅读文档**: iEDA 文档很详细
3. **多做实验**: 不同参数组合可能有不同结果
4. **记录问题**: 建立问题知识库
5. **参与社区**: 积极参与 iEDA 社区

---

> iEDA 作为国产开源数字后端平台，代表了中国在 EDA 领域的重要突破。虽然在集成过程中会遇到各种挑战，但这些挑战本身就是学习和成长的机会。希望我们的经验能够帮助更多人顺利使用 iEDA 进行芯片设计。
>
> 欢迎访问 [SiliconTrace Open 项目](https://github.com/silicontrace/silicontrace-open) 获取更多资源。
