# 硅迹开源 - 使用教程

> 本教程将带你从零开始，使用开源工具链完成从 RTL 代码到物理版图（GDSII）再到 PCB 测试载板的完整芯片设计流程。

---

## 目录

1. [项目简介](#1-项目简介)
2. [环境要求](#2-环境要求)
3. [环境搭建](#3-环境搭建)
4. [快速开始：一键运行全流程](#4-快速开始一键运行全流程)
5. [分步运行详解](#5-分步运行详解)
6. [AI 交互控制台使用](#6-ai-交互控制台使用)
7. [Docker 部署方式](#7-docker-部署方式)
8. [查看设计结果](#8-查看设计结果)
9. [导入自定义设计](#9-导入自定义设计)
10. [仿真与验证](#10-仿真与验证)
11. [常见问题](#11-常见问题)

---

## 1. 项目简介

**硅迹开源 (SiliconTrace)** 是一个完整的开源芯片设计项目，目标是让任何人都能在一台普通电脑上，仅使用开源工具完成：

- **RTL 综合**：将 Verilog HDL 代码综合为门级网表（Yosys）
- **数字后端**：布局布线，生成物理版图（iEDA）
- **PCB 设计**：设计测试载板，验证芯片功能（KiCad）

项目内置的设计案例是 **PicoRV32**，一个小型 RISC-V 处理器核心，约 3000 行 Verilog 代码，使用 SkyWater 130nm 工艺。

### 工具链概览

| 工具 | 用途 | 协议 |
|------|------|------|
| Yosys | RTL 综合 (Verilog → 门级网表) | ISC |
| iEDA | 国产开源数字后端平台 | Apache 2.0 |
| KiCad | 开源 PCB 设计 | GPL |
| SKY130 PDK | SkyWater 130nm 工艺设计套件 | Apache 2.0 |
| Icarus Verilog | Verilog 仿真器 | GPL |
| SymbiYosys | 形式验证工具 | ISC |

---

## 2. 环境要求

| 项目 | 推荐 | 最低 |
|------|------|------|
| 操作系统 | Ubuntu 22.04 (原生) | Ubuntu 22.04 (WSL2) |
| 内存 | 8GB+ | 4GB |
| 磁盘空间 | 10GB+ 可用 | - |
| CPU | 多核 (编译加速) | - |

---

## 3. 环境搭建

### 3.1 安装系统依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础依赖
sudo apt install -y build-essential cmake git curl wget python3 python3-pip

# 安装 EDA 相关依赖
sudo apt install -y libboost-all-dev libeigen3-dev libgoogle-glog-dev \
    libgflags-dev libtbb-dev libgtest-dev libgmp-dev tcl-dev tk-dev \
    flex bison autoconf automake libtool pkg-config

# 安装 KiCad
sudo apt install -y kicad
```

### 3.2 安装 Yosys

```bash
# 方式一：apt 安装（推荐）
sudo apt install -y yosys

# 方式二：源码编译（获取最新版）
git clone https://github.com/YosysHQ/yosys.git
cd yosys
make -j$(nproc)
sudo make install
```

验证安装：
```bash
yosys -V
# 输出示例：Yosys 0.64+...
```

### 3.3 安装 iEDA

iEDA 是国产开源数字后端平台，编译时间较长（约 30-60 分钟）。

```bash
cd ~
git clone https://github.com/OSCC-Project/iEDA.git
cd iEDA
mkdir build && cd build
cmake ..
make -j1  # 使用 -j1 避免内存不足；内存充足可用 -j$(nproc)
```

验证安装：
```bash
ls ~/iEDA/scripts/design/sky130_gcd/iEDA
```

### 3.4 安装 SKY130 PDK

```bash
pip3 install volare
volare enable --pdk sky130
```

验证安装：
```bash
ls ~/.volare/sky130A/
```

### 3.5 配置环境变量

```bash
cat >> ~/.bashrc << 'EOF'
export PDK_ROOT=$HOME/.volare
export IEDA_ROOT=$HOME/iEDA
export IEDA_BIN=$IEDA_ROOT/scripts/design/sky130_gcd/iEDA
export PATH=$IEDA_ROOT/scripts/design/sky130_gcd:$PATH
EOF
source ~/.bashrc
```

### 3.6 安装可选工具

```bash
# 查看 GDSII/DEF 版图
sudo apt install klayout

# 查看仿真波形
sudo apt install gtkwave

# Flask 前端依赖
pip3 install flask flask-cors
```

---

## 4. 快速开始：一键运行全流程

环境搭建完成后，最简单的方式是使用一键脚本，从 RTL 到 GDSII 全自动完成：

```bash
cd ~/SiliconTrace_Open

# 一键运行 RTL → GDSII 全流程
bash scripts/automation/run_full_flow.sh
```

该脚本会依次执行：

1. **Yosys 综合**：将 Verilog 源码综合为门级网表
2. **Floorplan**：创建布局区域、电源网络、IO 端口
3. **Placement**：全局布局 + 详细布局
4. **CTS**：时钟树综合
5. **Routing**：信号布线
6. **STA**：静态时序分析
7. **GDSII**：生成物理版图

运行完成后，查看输出文件：
```bash
ls synthesis/results/          # 综合输出（网表、JSON）
ls backend/result/             # 后端输出（DEF、GDSII）
ls backend/result/sta/         # 时序报告
```

---

## 5. 分步运行详解

如果你想了解每一步的细节，可以分步执行。

### 5.1 RTL 综合（Yosys）

综合是将 RTL 代码转换为由标准单元组成的门级网表的过程。

```bash
bash synthesis/run_synth.sh
```

**综合流程内部步骤：**

1. 读取 `rtl/picorv32/picorv32.v`（PicoRV32 RISC-V 处理器）
2. 执行 `proc` → `opt` → `flatten` → `memory_map`（寄存器文件展开）
3. 执行 `techmap` → `dfflibmap` → `abc`（映射到 SKY130 标准单元库）
4. 输出网表，并用 `fix_netlist.py` 修复复杂拼接赋值

**输出文件：**

| 文件 | 说明 |
|------|------|
| `synthesis/results/picorv32_netlist.v` | Verilog 门级网表 |
| `synthesis/results/picorv32_netlist.json` | JSON 格式网表 |
| `synthesis/results/picorv32.sdc` | 时序约束文件 |

### 5.2 后端流程（iEDA）

后端流程将门级网表转换为可制造的物理版图。

```bash
bash backend/run_ieda.sh
```

**后端流程详解：**

| 步骤 | 工具 | 说明 | 输出文件 |
|------|------|------|----------|
| Floorplan | iFP | 创建 1000μm×1000μm 布局区域，设置电源网络 | `iFP_result.def` |
| Placement | iPL | 将标准单元放置到布局区域内 | `iPL_result.def` |
| CTS | iCTS | 构建时钟树，插入时钟缓冲器 | `iCTS_result.def` |
| Routing | iRT | 信号布线（可能有 DRC 违例） | `final_design.def` |
| STA | iSTA | 静态时序分析 | `sta/picorv32.rpt` |
| GDSII | - | 生成物理版图 | `picorv32.gds2` |

**也可以单独运行某一步：**

```bash
# 只运行 Floorplan
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iFP.tcl

# 只运行 Placement
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iPL.tcl

# 只运行 STA
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iSTA.tcl
```

---

## 6. AI 交互控制台使用

硅迹开源提供了一个 Web 界面，可以通过自然语言命令控制整个设计流程。

### 6.1 启动控制台

```bash
pip3 install flask flask-cors
python3 frontend/app.py
```

浏览器访问：**http://localhost:5000**

### 6.2 控制台功能

- **流程可视化**：实时显示 7 个设计步骤的状态（综合 → Floorplan → Placement → CTS → Routing → STA → GDSII）
- **工具链检测**：自动检测 Yosys、iEDA、KiCad、PDK 等工具的安装状态
- **实时日志**：查看每一步的详细执行日志（SSE 流式推送）
- **设计切换**：支持多个 RTL 设计之间的切换和管理
- **文件导入**：支持导入自定义 RTL 设计、芯片封装、原理图符号

### 6.3 可用命令

在控制台输入框中输入以下命令：

| 命令 | 说明 |
|------|------|
| `综合` / `synthesis` / `yosys` | 运行 Yosys 综合 |
| `floorplan` / `fp` / `布局规划` | 运行 Floorplan |
| `placement` / `pl` / `布局` | 运行 Placement |
| `cts` / `时钟树` | 运行 CTS |
| `routing` / `rt` / `布线` | 运行 Routing |
| `sta` / `时序分析` | 运行 STA |
| `gdsii` / `gds` | 生成 GDSII |
| `全流程` / `full flow` | 运行完整 RTL→GDSII 流程 |
| `status` / `状态` | 查看项目状态 |
| `help` / `帮助` | 查看帮助信息 |

### 6.4 MCP 上传接口

控制台还提供 API 接口，支持通过命令行或脚本上传设计文件：

```bash
# 上传 RTL 设计
curl -X POST http://localhost:5000/api/upload/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "import",
    "type": "rtl",
    "filename": "my_design.v",
    "content": "module my_design(input clk, output reg [7:0] out); endmodule",
    "encoding": "text",
    "design_name": "my_design"
  }'
```

---

## 7. Docker 部署方式

如果你不想手动安装所有工具，可以使用 Docker 一键部署。

### 7.1 安装 Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

### 7.2 构建并启动

```bash
cd ~/SiliconTrace_Open

# 构建镜像（包含所有 EDA 工具，耗时较长）
docker compose -f docker/docker-compose.yml build

# 启动 EDA 环境 + AI 前端
docker compose -f docker/docker-compose.yml up -d
```

### 7.3 在容器中运行

```bash
# 进入 EDA 容器
docker exec -it silicontrace-eda bash

# 在容器内运行全流程
bash scripts/automation/run_full_flow.sh
```

### 7.4 访问 AI 控制台

```bash
docker compose -f docker/docker-compose.yml up frontend
# 浏览器访问：http://localhost:5000
```

---

## 8. 查看设计结果

### 8.1 查看综合结果

```bash
# 查看门级网表（前 50 行）
head -50 synthesis/results/picorv32_netlist.v

# 查看综合统计
grep -E "(wire|cell|module)" synthesis/results/picorv32_netlist.v | head -20
```

### 8.2 查看后端版图

```bash
# 使用 KLayout 查看 GDSII 物理版图
klayout backend/result/picorv32.gds2

# 使用 KLayout 查看 DEF 文件
klayout backend/result/iFP_result.def    # Floorplan
klayout backend/result/iPL_result.def    # Placement
klayout backend/result/iCTS_result.def   # CTS
```

### 8.3 查看时序报告

```bash
# 查看 STA 时序报告
cat backend/result/sta/picorv32.rpt

# 查看时钟偏斜报告
cat backend/result/sta/picorv32_setup.skew
cat backend/result/sta/picorv32_hold.skew
```

### 8.4 查看 PCB 设计

```bash
# 打开原理图
kicad kicad/test_board/test_board.kicad_sch

# 打开 PCB Layout（4 层板，40mm × 30mm）
kicad kicad/test_board/test_board.kicad_pcb
```

### 8.5 输出文件汇总

| 阶段 | 输出文件 | 查看方式 |
|------|----------|----------|
| 综合 | `synthesis/results/picorv32_netlist.v` | Vim / VS Code |
| 综合 | `synthesis/results/picorv32_netlist.json` | Vim / VS Code |
| Floorplan | `backend/result/iFP_result.def` | KLayout |
| Placement | `backend/result/iPL_result.def` | KLayout |
| CTS | `backend/result/iCTS_result.def` | KLayout |
| GDSII | `backend/result/picorv32.gds2` | KLayout |
| STA | `backend/result/sta/picorv32.rpt` | Vim / VS Code |
| PCB | `kicad/test_board/test_board.kicad_pcb` | KiCad |

---

## 9. 导入自定义设计

除了默认的 PicoRV32，你可以导入自己的 RTL 设计。

### 9.1 通过 Web 控制台

1. 启动控制台：`python3 frontend/app.py`
2. 在浏览器中打开 http://localhost:5000
3. 使用文件导入功能上传 RTL 文件

### 9.2 通过命令行

将你的 Verilog 文件放入 `rtl/` 目录：

```bash
cp my_design.v rtl/my_design/
```

然后修改综合脚本中的源文件路径，或在 AI 控制台中切换设计。

### 9.3 通过 API 上传

```bash
curl -X POST http://localhost:5000/api/upload/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "import",
    "type": "rtl",
    "filename": "my_design.v",
    "content": "<你的 Verilog 代码>",
    "encoding": "text",
    "design_name": "my_design"
  }'
```

---

## 10. 仿真与验证

### 10.1 功能仿真

```bash
# 安装 Icarus Verilog
sudo apt install -y iverilog

# 运行仿真
cd tests/simulation
make sim

# 查看波形（需要 GTKWave）
sudo apt install gtkwave
make wave
```

### 10.2 形式验证

```bash
# 安装 SymbiYosys
pip3 install symbiyosys

# 运行 BMC 验证
cd tests/formal
bash run_formal.sh
```

---

## 11. 常见问题

### Q1: iEDA 编译失败（内存不足）

**解决方案：** 使用 `make -j1` 单线程编译，或增加 swap 空间。

### Q2: Routing 有 DRC 违例

**说明：** 在 7.7GB 内存环境下，布线约有 5600 个 DRC 违例，这是已知限制。增大内存或降低设计密度（修改 `backend/config/pl_default_config.json` 中的 density 参数）可改善。

### Q3: 综合报错 "No such cell"

**解决方案：** 检查 PDK 路径是否正确：
```bash
echo $PDK_ROOT
ls $PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/lib/
```

### Q4: KiCad 文件打不开

**解决方案：** 确保使用 KiCad 6.0+ 版本。

### Q5: Docker 构建失败

**解决方案：** 确保有足够的磁盘空间（约 10GB）和内存（约 4GB）。

### Q6: STA 时序不满足

**说明：** STA 报告中 Slack 为负值表示时序违例。在 PicoRV32 设计中，由于工艺和布局限制，可能无法满足所有时序约束。可以尝试降低时钟频率或优化布局密度。

---

## 附录：项目目录结构

```
SiliconTrace_Open/
├── rtl/                    # RTL 源代码
│   └── picorv32/           # PicoRV32 RISC-V 处理器
├── synthesis/              # Yosys 综合
│   ├── run_synth.sh        # 综合运行脚本
│   ├── constraints/        # SDC 时序约束
│   └── results/            # 综合输出
├── backend/                # iEDA 后端流程
│   ├── tcl/                # iEDA Tcl 脚本
│   ├── config/             # 配置文件
│   ├── run_ieda.sh         # 后端全流程脚本
│   └── result/             # 后端输出
├── kicad/                  # KiCad PCB 设计
│   ├── test_board/         # 测试载板
│   ├── symbols/            # 原理图符号库
│   └── footprints/         # 封装库
├── frontend/               # AI 交互控制台
│   ├── app.py              # Flask 后端
│   └── templates/          # Web 前端
├── scripts/                # 自动化脚本
│   ├── yosys2ieda/         # 网表转换
│   └── automation/         # 全流程脚本
├── tests/                  # 测试
│   ├── simulation/         # 仿真测试
│   └── formal/             # 形式验证
├── docker/                 # Docker 环境
└── docs/                   # 文档
```

---

*硅迹开源 - 让芯片设计不再是少数人的特权。*
