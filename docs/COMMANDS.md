# 硅迹开源 - 完整命令手册

本文档详细说明数字 IC 前端、后端到 PCB 测试板的全部命令流程。

---

## 目录

1. [环境准备](#1-环境准备)
2. [RTL 综合 (Yosys)](#2-rtl-综合-yosys)
3. [后端流程 (iEDA)](#3-后端流程-ieda)
4. [PCB 测试载板 (KiCad)](#4-pcb-测试载板-kicad)
5. [仿真测试](#5-仿真测试)
6. [形式验证](#6-形式验证)
7. [Docker 环境](#7-docker-环境)
8. [AI 交互控制台](#8-ai-交互控制台)
9. [全流程一键运行](#9-全流程一键运行)

---

## 1. 环境准备

### 1.1 系统依赖安装

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

**输出日志示例:**
```
[2026-04-30 10:00:00] [info] 更新系统软件包列表...
[2026-04-30 10:00:05] [info] 安装 build-essential...
[2026-04-30 10:00:30] [success] 系统依赖安装完成
```

### 1.2 Yosys 安装

```bash
# 方法 1: apt 安装
sudo apt install -y yosys

# 方法 2: 源码编译
git clone https://github.com/YosysHQ/yosys.git
cd yosys
make -j$(nproc)
sudo make install
```

**验证:**
```bash
yosys -V
# 输出: Yosys 0.64+172 (Ubuntu 0.64+172build1)
```

### 1.3 iEDA 安装

```bash
# 克隆源码
cd ~
git clone https://github.com/OSCC-Project/iEDA.git
cd iEDA

# 编译 (使用 -j1 避免内存不足)
mkdir build && cd build
cmake ..
make -j1  # 约 30-60 分钟

# 验证
ls -la ~/iEDA/scripts/design/sky130_gcd/iEDA
```

**输出日志示例:**
```
[10:00:00] [info] 开始编译 iEDA...
[10:00:05] [info] [1%] Building CXX object...
...
[10:45:00] [info] [100%] Linking CXX executable iEDA
[10:45:01] [success] iEDA 编译完成
```

### 1.4 SKY130 PDK 安装

```bash
pip install volare
volare enable --pdk sky130

# 验证
ls ~/.volare/sky130A/
```

### 1.5 环境变量配置

```bash
# 创建环境配置文件
cat > ~/.eda_env << 'EOF'
export PDK_ROOT=$HOME/.volare
export IEDA_ROOT=$HOME/iEDA
export IEDA_BIN=$IEDA_ROOT/scripts/design/sky130_gcd/iEDA
export PATH=$IEDA_ROOT/scripts/design/sky130_gcd:$PATH
EOF

# 添加到 bashrc
echo "source ~/.eda_env" >> ~/.bashrc
source ~/.bashrc
```

---

## 2. RTL 综合 (Yosys)

### 2.1 运行综合

```bash
cd ~/SiliconTrace_Open
bash synthesis/run_synth.sh
```

**执行步骤与日志输出:**

```
==========================================
 硅迹开源 - Yosys 综合
==========================================
[10:00:00] [info] 步骤 1: 生成综合脚本
[10:00:00] [info] PDK 库路径: ~/.volare/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
[10:00:01] [info] 步骤 2: 运行 Yosys 综合
[10:00:01] [info] Yosys 0.64+172
[10:00:02] [info] 读取 RTL 源码: rtl/picorv32/picorv32.v
[10:00:03] [info] 执行 pass: proc
[10:00:05] [info] 执行 pass: opt
[10:00:06] [info] 执行 pass: flatten
[10:00:08] [info] 执行 pass: memory_map (展开寄存器文件)
[10:00:15] [info] 执行 pass: techmap
[10:00:20] [info] 执行 pass: dfflibmap -liberty sky130_fd_sc_hd
[10:00:25] [info] 执行 pass: abc -liberty sky130_fd_sc_hd
[10:00:45] [info] 写入网表: artifacts/synthesis/picorv32_netlist.v
[10:00:46] [info] 写入 JSON: artifacts/synthesis/picorv32_netlist.json
[10:00:47] [info] 步骤 3: 后处理网表 (fix_netlist.py)
[10:00:47] [info] 展开复杂拼接赋值...
[10:00:48] [info] 处理了 156 个拼接赋值
[10:00:49] [info] 步骤 4: 复制 SDC 约束文件
[10:00:49] [success] 综合完成!
[10:00:49] [info] 输出文件:
[10:00:49] [info]   - artifacts/synthesis/picorv32_netlist.v (839KB)
[10:00:49] [info]   - artifacts/synthesis/picorv32_netlist.json (2.9MB)
[10:00:49] [info]   - artifacts/synthesis/picorv32.sdc
```

### 2.2 输出文件说明

| 文件 | 大小 | 说明 | 查看方式 |
|------|------|------|---------|
| `artifacts/synthesis/picorv32_netlist.v` | 839KB | 综合后 Verilog 网表 | `vim` / `code` |
| `artifacts/synthesis/picorv32_netlist.json` | 2.9MB | JSON 格式网表 | `vim` / `code` |
| `artifacts/synthesis/picorv32.sdc` | 378B | 时序约束文件 | `vim` / `code` |

### 2.3 验证综合结果

```bash
# 查看网表
head -50 artifacts/synthesis/picorv32_netlist.v

# 查看统计信息
grep -E "(wire|cell|module)" artifacts/synthesis/picorv32_netlist.v | head -20
```

---

## 3. 后端流程 (iEDA)

### 3.1 一键运行全流程

```bash
cd ~/SiliconTrace_Open
bash backend/run_ieda.sh
```

### 3.2 分步运行

#### 步骤 1: Floorplan (布局规划)

```bash
export CONFIG_DIR=backend/config
export RESULT_DIR=artifacts/backend
export TCL_SCRIPT_DIR=~/iEDA/scripts/design/sky130_gcd/script
export CUSTOM_TCL_DIR=backend/tcl
export NETLIST_FILE=artifacts/synthesis/picorv32_netlist.v
export SDC_FILE=synthesis/constraints/picorv32.sdc
export DESIGN_TOP=picorv32
export DIE_AREA="0.0 0.0 1000.0 1000.0"
export CORE_AREA="10.0 10.0 990.0 990.0"

mkdir -p artifacts/backend/report artifacts/backend/rt

~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iFP.tcl
```

**日志输出:**
```
[10:01:00] [info] === Floorplan (iFP) ===
[10:01:00] [info] 步骤 1: 初始化流程配置
[10:01:01] [info] Init Flow Config success.
[10:01:01] [info] 步骤 2: 读取 LEF/DEF 库文件
[10:01:02] [info] 读取 tech LEF: sky130_fd_sc_hd.tlef
[10:01:03] [info] 读取 cell LEF: sky130_fd_sc_hd_merged.lef
[10:01:05] [info] 步骤 3: 读取综合网表
[10:01:06] [info] Read Verilog file success
[10:01:07] [info] 步骤 4: 创建布局区域
[10:01:07] [info] Die area: 0.0 0.0 1000.0 1000.0
[10:01:07] [info] Core area: 10.0 10.0 990.0 990.0
[10:01:08] [info] 步骤 5: 创建轨道 (Tracks)
[10:01:09] [info] 步骤 6: 设置电源网络 (PDN)
[10:01:10] [info] 创建 VDD/VSS 电源端口
[10:01:11] [info] 创建 met1 网格
[10:01:12] [info] 创建 met4/met5 条纹
[10:01:15] [info] 步骤 7: 放置 IO 端口
[10:01:16] [info] 步骤 8: 放置 Tap 单元
[10:01:18] [info] 步骤 9: 保存 DEF
[10:01:19] [success] Floorplan 完成! 输出: artifacts/backend/iFP_result.def
```

#### 步骤 2: Placement (布局)

```bash
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iPL.tcl
```

**日志输出:**
```
[10:02:00] [info] === Placement (iPL) ===
[10:02:00] [info] 步骤 1: 读取 Floorplan DEF
[10:02:01] [info] 步骤 2: 全局布局 (Global Placement)
[10:02:02] [info] [NesterovSolve] Iter: 1 overflow: 0.96 HPWL: 116230349
[10:02:05] [info] [NesterovSolve] Iter: 100 overflow: 0.45 HPWL: 136768857
[10:02:10] [info] [NesterovSolve] Iter: 200 overflow: 0.12 HPWL: 145000000
[10:02:15] [info] 步骤 3: 详细布局 (Detailed Placement)
[10:02:20] [info] 步骤 4: 插入填充单元 (Filler)
[10:02:25] [info] 步骤 5: 保存 DEF
[10:02:26] [success] Placement 完成! 输出: artifacts/backend/iPL_result.def
```

#### 步骤 3: CTS (时钟树综合)

```bash
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iCTS.tcl
```

**日志输出:**
```
[10:03:00] [info] === CTS (iCTS) ===
[10:03:00] [info] 步骤 1: 读取 Placement DEF
[10:03:01] [info] 步骤 2: 构建时钟树
[10:03:05] [info] 步骤 3: 插入时钟缓冲器
[10:03:10] [info] 步骤 4: 时钟树平衡
[10:03:15] [info] 步骤 5: 保存 DEF
[10:03:16] [success] CTS 完成! 输出: artifacts/backend/iCTS_result.def
```

#### 步骤 4: Routing (布线)

```bash
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iRT.tcl
```

**日志输出:**
```
[10:04:00] [info] === Routing (iRT) ===
[10:04:00] [info] 步骤 1: 读取 CTS DEF
[10:04:01] [info] 步骤 2: 初始化布线器
[10:04:01] [info] 底层: met1, 顶层: met4, 线程数: 4
[10:04:02] [info] 步骤 3: 全局布线
[10:04:10] [info] 步骤 4: 详细布线
[10:04:30] [info] 步骤 5: DRC 检查
[10:04:45] [warning] 注意: 存在 DRC 违例 (pin access 问题)
[10:04:46] [info] 步骤 6: 保存 DEF
[10:04:47] [info] Routing 完成 (有 DRC 违例)
```

**注意:** 在 7.7GB 内存环境下，Routing 可能有约 5600 个 DRC 违例。这是已知限制。

#### 步骤 5: STA (静态时序分析)

```bash
# 使用 CTS 结果 (如果 Routing 未完成)
export INPUT_DEF=artifacts/backend/iCTS_result.def
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_iSTA.tcl
```

**日志输出:**
```
[10:05:00] [info] === STA (iSTA) ===
[10:05:00] [info] 步骤 1: 读取 DEF
[10:05:01] [info] 步骤 2: 加载 Liberty 时序库
[10:05:02] [info] 加载: sky130_fd_sc_hd__tt_025C_1v80.lib
[10:05:05] [info] 步骤 3: 建立时序图
[10:05:10] [info] 步骤 4: 计算路径延迟
[10:05:15] [info] 步骤 5: 生成时序报告
[10:05:16] [info] 
+-----------+-------------+------------+------------+---------------+-------+--------+-----------+
| Endpoint  | Clock Group | Delay Type | Path Delay | Path Required | CPPR  | Slack  | Freq(MHz) |
+-----------+-------------+------------+------------+---------------+-------+--------+-----------+
| _10344_:D | clk         | max        | 18.623r    | 9.825         | 0.000 | -8.798 | 53.198    |
+-----------+-------------+------------+------------+---------------+-------+--------+-----------+
[10:05:17] [success] STA 完成!
[10:05:17] [info] 输出:
[10:05:17] [info]   - artifacts/backend/sta/picorv32.rpt (时序报告)
[10:05:17] [info]   - artifacts/backend/sta/picorv32_setup.skew
[10:05:17] [info]   - artifacts/backend/sta/picorv32_hold.skew
```

#### 步骤 6: GDSII 生成

```bash
export INPUT_DEF=artifacts/backend/iCTS_result.def
~/iEDA/scripts/design/sky130_gcd/iEDA -script backend/tcl/run_def_to_gds.tcl
```

**日志输出:**
```
[10:06:00] [info] === 生成 GDSII ===
[10:06:00] [info] 步骤 1: 读取 DEF
[10:06:01] [info] 步骤 2: 转换为 GDSII 格式
[10:06:05] [info] 写入 GDSII 文件...
[10:06:30] [success] GDSII 生成完成! 输出: artifacts/backend/picorv32.gds2 (87MB)
```

### 3.3 输出文件说明

| 文件 | 大小 | 说明 | 查看方式 |
|------|------|------|---------|
| `artifacts/backend/iFP_result.def` | 5.1MB | Floorplan DEF | `vim` / KLayout |
| `artifacts/backend/iPL_result.def` | 5.3MB | Placement DEF | `vim` / KLayout |
| `artifacts/backend/iCTS_result.def` | 5.3MB | CTS DEF | `vim` / KLayout |
| `artifacts/backend/iRT_result.def` | - | Routing DEF (如有) | `vim` / KLayout |
| `artifacts/backend/final_design.def` | 5.3MB | 最终 DEF | `vim` / KLayout |
| `artifacts/backend/final_design.v` | 1.5MB | 最终 Verilog 网表 | `vim` / `code` |
| `artifacts/backend/picorv32.gds2` | 87MB | GDSII 物理版图 | KLayout |
| `artifacts/backend/sta/picorv32.rpt` | 53KB | STA 时序报告 | `vim` / `code` |
| `artifacts/backend/sta/*.skew` | 14KB | 时钟偏斜报告 | `vim` / `code` |

### 3.4 查看结果

```bash
# 查看 STA 报告
cat artifacts/backend/sta/picorv32.rpt | head -50

# 使用 KLayout 查看 GDSII
klayout artifacts/backend/picorv32.gds2

# 使用 KLayout 查看 DEF
klayout artifacts/backend/final_design.def
```

---

## 4. PCB 测试载板 (KiCad)

### 4.1 查看原理图

```bash
kicad kicad/test_board/test_board.kicad_sch
```

**原理图包含:**
- PicoRV32 (QFN-48) 实例
- 去耦电容 C3-C6 (100nF, 10uF)
- 100MHz 晶振 Y1
- 复位电路 (R1 上拉 + SW1 按键)
- JTAG 接口 J1 (6pin)
- GPIO 排针 J2 (8pin)
- LDO 稳压器 U2 (3.3V)
- 电源电容 C8, C9

### 4.2 查看 PCB Layout

```bash
kicad kicad/test_board/test_board.kicad_pcb
```

**PCB 参数:**
- 尺寸: 40mm x 30mm
- 层叠: 4 层 (F.Cu / In1.Cu / In2.Cu / B.Cu)
- 材质: FR4, ENIG 表面处理
- 安装孔: 4 个 M2 (2.2mm)

### 4.3 查看符号和封装

```bash
# 符号编辑器
kicad kicad/symbols/picorv32.kicad_sym

# 封装编辑器
kicad kicad/footprints/QFN-48_7x7mm_P0.5mm.kicad_mod
```

---

## 5. 仿真测试

### 5.1 运行仿真

```bash
cd ~/SiliconTrace_Open/tests/simulation

# 需要安装 Icarus Verilog
sudo apt install iverilog

# 运行仿真
make sim

# 查看波形 (需要 GTKWave)
sudo apt install gtkwave
make wave
```

**日志输出:**
```
[10:10:00] [info] 编译测试平台...
[10:10:01] [info] iverilog -o sim.vvp tb_picorv32.v ../../rtl/picorv32/picorv32.v
[10:10:05] [info] 运行仿真...
[10:10:06] [info] vvp sim.vvp
[10:10:10] [info] 仿真完成
[10:10:10] [info] 波形文件: dump.vcd
```

### 5.2 输出文件

| 文件 | 说明 | 查看方式 |
|------|------|---------|
| `tests/simulation/sim.vvp` | 编译后仿真文件 | - |
| `tests/simulation/dump.vcd` | 波形文件 | GTKWave |

---

## 6. 形式验证

### 6.1 运行形式验证

```bash
cd ~/SiliconTrace_Open/tests/formal

# 需要安装 SymbiYosys
pip install symbiyosys

# 运行 BMC 验证
bash run_formal.sh
```

**日志输出:**
```
[10:15:00] [info] === 形式验证 ===
[10:15:00] [info] 运行 BMC (有界模型检验)...
[10:15:01] [info] sby -f picorv32.sby bmc
[10:15:30] [info] BMC 验证通过
[10:15:31] [success] 形式验证完成
```

---

## 7. Docker 环境

### 7.1 安装 Docker

```bash
# 安装 Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 添加 Docker GPG 密钥
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 添加 Docker 源
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 将用户添加到 docker 组
sudo usermod -aG docker $USER
newgrp docker

# 验证
docker --version
docker compose version
```

### 7.2 构建 Docker 镜像

```bash
cd ~/SiliconTrace_Open

# 构建镜像
docker compose -f docker/docker-compose.yml build

# 或直接构建
docker build -t silicontrace:latest -f docker/Dockerfile .
```

**日志输出:**
```
[+] Building 1200.5s (15/15) FINISHED
 => [internal] load build definition from Dockerfile
 => [internal] load .dockerignore
 => [1/10] FROM ubuntu:22.04
 => [2/10] RUN apt-get update && apt-get install -y build-essential cmake...
 => [3/10] RUN apt-get install -y yosys
 => [4/10] RUN apt-get install -y kicad
 => [5/10] RUN pip3 install volare symbiyosys flask
 => [6/10] RUN volare enable --pdk sky130
 => [7/10] RUN cd /opt && git clone iEDA && make -j$(nproc)
 => [8/10] COPY . /workspace/
 => exporting to image
 => => writing image sha256:abc123...
 => => naming to docker.io/library/silicontrace:latest
```

### 7.3 运行 Docker 容器

```bash
# 启动 EDA 环境
docker compose -f docker/docker-compose.yml up -d

# 进入容器
docker exec -it silicontrace-eda bash

# 在容器内运行综合
bash synthesis/run_synth.sh

# 在容器内运行后端
bash backend/run_ieda.sh
```

### 7.4 Docker 常用命令

```bash
# 查看运行中的容器
docker ps

# 查看所有容器
docker ps -a

# 停止容器
docker compose -f docker/docker-compose.yml down

# 查看日志
docker logs silicontrace-eda

# 进入容器
docker exec -it silicontrace-eda bash

# 删除容器
docker rm silicontrace-eda

# 删除镜像
docker rmi silicontrace:latest
```

---

## 8. AI 交互控制台

### 8.1 启动控制台

```bash
cd ~/SiliconTrace_Open

# 方法 1: 直接运行
python3 frontend/app.py

# 方法 2: Docker 运行
docker compose -f docker/docker-compose.yml up frontend
```

### 8.2 访问控制台

打开浏览器访问: http://localhost:5000

### 8.3 可用命令

| 命令 | 说明 |
|------|------|
| `综合` / `synthesis` / `yosys` | 运行 Yosys 综合 |
| `floorplan` / `fp` / `布局规划` | 运行 Floorplan |
| `placement` / `pl` / `布局` | 运行 Placement |
| `cts` / `时钟树` | 运行 CTS |
| `routing` / `rt` / `布线` | 运行 Routing |
| `sta` / `时序分析` | 运行 STA |
| `gdsii` / `gds` | 生成 GDSII |
| `全流程` / `full flow` / `rtl2gds` | 运行完整流程 |
| `kicad` / `检查kicad` | 检查 KiCad 文件 |
| `status` / `状态` | 查看项目状态 |

### 8.4 API 接口

```bash
# 执行命令
curl -X POST http://localhost:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "综合"}'

# 获取日志
curl http://localhost:5000/api/logs

# 获取状态
curl http://localhost:5000/api/status

# 获取帮助
curl http://localhost:5000/api/help
```

---

## 9. 全流程一键运行

### 9.1 使用脚本

```bash
cd ~/SiliconTrace_Open
bash scripts/automation/run_full_flow.sh
```

### 9.2 使用 AI 控制台

1. 启动控制台: `python3 frontend/app.py`
2. 打开浏览器: http://localhost:5000
3. 输入命令: `全流程` 或 `full flow`

### 9.3 完整日志输出示例

```
========================================
  硅迹开源 - RTL→GDSII 全流程
========================================

>>> 开始: Yosys 综合 <<<
[10:00:00] [info] === 开始 Yosys 综合 ===
[10:00:01] [info] 读取 RTL 源码...
[10:00:05] [info] 执行 synthesis pass...
[10:00:45] [success] 综合完成!

>>> 开始: Floorplan <<<
[10:01:00] [info] === 开始 Floorplan (iFP) ===
[10:01:01] [info] 创建 1000um x 1000um 布局区域
[10:01:19] [success] Floorplan 完成!

>>> 开始: Placement <<<
[10:02:00] [info] === 开始 Placement (iPL) ===
[10:02:01] [info] 全局布局中...
[10:02:26] [success] Placement 完成!

>>> 开始: CTS <<<
[10:03:00] [info] === 开始 CTS (iCTS) ===
[10:03:16] [success] CTS 完成!

>>> 开始: Routing <<<
[10:04:00] [info] === 开始 Routing (iRT) ===
[10:04:47] [warning] Routing 完成 (有 DRC 违例)

>>> 开始: STA <<<
[10:05:00] [info] === 开始 STA (iSTA) ===
[10:05:17] [success] STA 完成!

>>> 开始: GDSII <<<
[10:06:00] [info] === 生成 GDSII ===
[10:06:30] [success] GDSII 生成完成!

========================================
  全流程完成!
========================================

输出文件:
- artifacts/synthesis/picorv32_netlist.v
- artifacts/backend/iFP_result.def
- artifacts/backend/iPL_result.def
- artifacts/backend/iCTS_result.def
- artifacts/backend/final_design.def
- artifacts/backend/final_design.v
- artifacts/backend/picorv32.gds2
- artifacts/backend/sta/picorv32.rpt
```

---

## 附录: 常见问题

### Q1: iEDA 编译失败 (OOM)
**解决方案:** 使用 `make -j1` 单线程编译

### Q2: Routing 有 DRC 违例
**解决方案:** 这是 7.7GB 内存环境下的已知限制。增大内存或降低设计密度。

### Q3: KiCad 文件打不开
**解决方案:** 确保使用 KiCad 7+，文件中不能有 `;;` 注释。

### Q4: Docker 构建失败
**解决方案:** 确保有足够的磁盘空间 (约 10GB) 和内存 (约 4GB)。

### Q5: 综合报错 "No such cell"
**解决方案:** 检查 PDK 路径是否正确设置。
