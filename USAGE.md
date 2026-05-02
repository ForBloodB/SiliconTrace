# 硅迹开源 - 使用说明

## 快速开始

### 环境要求
- Ubuntu 22.04 (WSL2 或原生)
- 内存：建议 8GB+（最低 4GB）
- 磁盘：约 10GB 空闲空间

### 1. 环境配置
```bash
# 安装系统依赖
sudo apt update
sudo apt install -y build-essential cmake libboost-all-dev libeigen3-dev \
    libgoogle-glog-dev libgflags-dev libtbb-dev libgtest-dev libgmp-dev \
    kicad python3-pip

# 安装 Yosys
sudo apt install -y yosys

# 安装 iEDA（源码编译，约 30-60 分钟）
cd ~
git clone https://github.com/OSCC-Project/iEDA.git
cd iEDA
mkdir build && cd build
cmake ..
make -j1  # 使用 -j1 避免内存不足

# 安装 SKY130 PDK
pip install volare
volare enable --pdk sky130
```

### 2. 运行 RTL→GDSII 全流程
```bash
cd ~/SiliconTrace_Open

# 步骤 1: Yosys 综合
bash synthesis/run_synth.sh

# 步骤 2: iEDA 后端（FP→PL→CTS→RT→STA→GDSII）
bash backend/run_ieda.sh
```

### 3. 运行第二个示例设计
```bash
# 小型 blinky_counter 示例，用来验证流程不只支持 PicoRV32
DESIGN_TOP=blinky_counter bash synthesis/run_synth.sh
DESIGN_TOP=blinky_counter EXPORT_KICAD=0 bash backend/run_ieda.sh

# 验证 routing / STA 是否干净
cat artifacts/backend/blinky_counter/rt/route_status.txt
grep -E "clk[[:space:]]+\\|[[:space:]]+(max|min)" artifacts/backend/blinky_counter/sta/blinky_counter.rpt
```

### 4. 查看 KiCad 测试载板
```bash
# 后端流程会自动生成 KiCad 工程，也可以单独重新导出
python3 backend/export_kicad.py

# 打开生成的原理图
kicad artifacts/kicad/picorv32_test_board/picorv32_test_board.kicad_sch

# 打开生成的 PCB Layout
kicad artifacts/kicad/picorv32_test_board/picorv32_test_board.kicad_pcb
```

---

## 各阶段生成文件说明

### 综合阶段 (artifacts/synthesis/)
| 文件 | 说明 | 查看方式 |
|------|------|---------|
| `picorv32_netlist.v` | 综合后 Verilog 网表 | `vim` / `code` |
| `picorv32_netlist.json` | JSON 格式网表 | `vim` / `code` |
| `picorv32.sdc` | 时序约束文件 | `vim` / `code` |

### 后端阶段 (artifacts/backend/)
| 文件 | 说明 | 查看方式 |
|------|------|---------|
| `iFP_result.def` | Floorplan DEF 文件 | `vim` / KLayout |
| `iPL_result.def` | 布局 DEF 文件 | `vim` / KLayout |
| `iCTS_result.def` | 时钟树 DEF 文件 | `vim` / KLayout |
| `iRT_result.def` | 布线 DEF 文件（routing 完成后生成，DRC>0 时仍可用） | `vim` / KLayout |
| `rt/route_status.txt` | Routing 成败与 DRC 数量 | `cat` |
| `final_design.def` | 最终 DEF 文件 | `vim` / KLayout |
| `final_design.v` | 最终 Verilog 网表 | `vim` / `code` |
| `picorv32.gds2` | GDSII 物理版图 | KLayout |
| `sta/picorv32.rpt` | STA 时序报告 | `vim` / `code` |
| `sta/*.skew` | 时钟偏斜报告 | `vim` / `code` |
| `report/*.rpt` | 各阶段数据库报告 | `vim` / `code` |

### KiCad 文件
| 文件 | 说明 | 查看方式 |
|------|------|---------|
| `artifacts/kicad/picorv32_test_board/picorv32_test_board.kicad_sch` | 自动导出的原理图 | KiCad (kicad 命令) |
| `artifacts/kicad/picorv32_test_board/picorv32_test_board.kicad_pcb` | 自动导出的 PCB Layout | KiCad (kicad 命令) |
| `artifacts/kicad/picorv32_test_board/pin_map.csv` | symbol pin 到 PCB net 的映射 | `vim` / `code` |
| `test_board/test_board.kicad_sch` | 原理图 | KiCad (kicad 命令) |
| `test_board/test_board.kicad_pcb` | PCB Layout | KiCad (kicad 命令) |
| `symbols/picorv32.kicad_sym` | PicoRV32 符号 | KiCad 符号编辑器 |
| `footprints/QFN-48_7x7mm_P0.5mm.kicad_mod` | QFN-48 封装 | KiCad 封装编辑器 |

### 测试文件 (tests/)
| 文件 | 说明 | 查看方式 |
|------|------|---------|
| `simulation/tb_picorv32.v` | 仿真测试平台 | `vim` / `code` |
| `simulation/test.hex` | 测试程序 | `vim` / `code` |
| `simulation/Makefile` | 仿真构建脚本 | `vim` / `code` |
| `formal/picorv32.sby` | SymbiYosys 配置 | `vim` / `code` |
| `formal/properties.v` | 形式验证属性 | `vim` / `code` |

---

## 常用工具安装

### KLayout（查看 GDSII/DEF）
```bash
sudo apt install klayout
# 打开 GDSII 文件
klayout artifacts/backend/picorv32.gds2
```

### GTKWave（查看仿真波形）
```bash
sudo apt install gtkwave
# 仿真后查看波形
gtkwave tests/simulation/dump.vcd
```

### SymbiYosys（形式验证）
```bash
pip install symbiyosys
# 运行形式验证
cd tests/formal
bash run_formal.sh
```

---

## 项目架构

```
RTL (PicoRV32)
    │
    ▼
Yosys 综合 ──→ Verilog 网表 + SDC 约束
    │
    ▼
iEDA 后端
    ├── Floorplan (iFP) ──→ 布局规划
    ├── Placement (iPL) ──→ 标准单元布局
    ├── CTS (iCTS) ──→ 时钟树综合
    ├── Routing (iRT) ──→ 布线（route_status.txt 判定成败）
    ├── STA (iSTA) ──→ 静态时序分析
    └── GDSII ──→ 物理版图
    │
    ▼
KiCad 测试载板
    ├── 原理图 (.kicad_sch)
    └── PCB Layout (.kicad_pcb)
```

---

## 已知限制

1. **PicoRV32 Routing 尚未清零**：当前 PicoRV32 后端结果仍有 routing DRC（约 12K-15K），脚本会返回非零并输出 `iRT_result.def`（含 DRC 的 routed DEF）；STA/GDS 仍会使用该 DEF 生成结果（仅用于调试/展示，不代表 clean closure）；`blinky_counter` 示例已验证 routing DRC=0、STA max/min TNS=0。
2. **SDC 约束简化**：iEDA STA 仅支持基本 SDC 命令。
3. **单元库**：使用 HD（高密度）库，HS 库可能时序更优。

---

## Git 信息

- 提交者：Mufire-star <1269897690@qq.com>
- 分支：main
- 提交数：5（含后续更新）
