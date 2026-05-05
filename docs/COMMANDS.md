# 硅迹开源 - 完整命令手册

本文档详细说明数字 IC 设计流程的全部命令，基于 LibreLane/OpenROAD 后端流程。

---

## 目录

1. [环境准备](#1-环境准备)
2. [RTL 综合 (Yosys)](#2-rtl-综合-yosys)
3. [后端流程 (LibreLane/OpenROAD)](#3-后端流程-librelaneopenroad)
4. [Signoff 检查 (DRC/LVS/XOR)](#4-signoff-检查-drclvsxor)
5. [KiCad PCB 输出](#5-kicad-pcb-输出)
6. [仿真测试](#6-仿真测试)
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

# 安装 KiCad
sudo apt install -y kicad

# 安装 Python 工具
pip3 install librelane volare
```

### 1.2 Yosys 安装

```bash
# 方法 1: apt 安装 (推荐)
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

### 1.3 SKY130 PDK 安装

```bash
volare enable --pdk sky130

# 验证
ls ~/.volare/sky130A/
```

### 1.4 工具验证

```bash
# 检查所有必需工具
which yosys librelane magic klayout

# 检查 Python 包
pip list | grep -E "librelane|volare"
```

---

## 2. RTL 综合 (Yosys)

### 2.1 运行综合

```bash
cd ~/SiliconTrace
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
[10:00:47] [success] 综合完成!
```

### 2.2 输出文件说明

| 文件 | 大小 | 说明 | 查看方式 |
|------|------|------|---------|
| `artifacts/synthesis/picorv32_netlist.v` | ~800KB | 综合后 Verilog 网表 | `vim` / `code` |
| `artifacts/synthesis/picorv32_netlist.json` | ~3MB | JSON 格式网表 | `vim` / `code` |

---

## 3. 后端流程 (LibreLane/OpenROAD)

### 3.1 运行 PicoRV32 完整流程

```bash
cd ~/SiliconTrace

# 运行 PicoRV32 (使用默认配置)
bash scripts/run_picorv32_librelane.sh sky130_picorv32

# 或者使用自定义 run tag
bash scripts/run_picorv32_librelane.sh my_custom_run
```

### 3.2 运行 SERV 完整流程

```bash
cd ~/SiliconTrace

# 运行 SERV
bash scripts/run_serv_librelane.sh sky130_test
```

### 3.3 查看运行结果

```bash
# 查看 PicoRV32 结果目录
ls artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/

# 查看 SERV 结果目录
ls artifacts/librelane/serv_sky130/runs/sky130_test/final/
```

### 3.4 查看运行指标

```bash
# 查看 PicoRV32 指标
cat artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/metrics.json | python3 -m json.tool

# 关键指标:
# - route__drc_errors: 0 (布线 DRC 错误)
# - magic__drc_error__count: 0 (Magic DRC 错误)
# - klayout__drc_error__count: 0 (KLayout DRC 错误)
# - design__lvs_error__count: 0 (LVS 错误)
# - design__xor_difference__count: 0 (XOR 差异)
```

### 3.5 查看 GDSII 版图

```bash
# 使用 KLayout 查看
klayout artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/gds/picorv32.gds
```

### 3.6 查看渲染图

```bash
# 查看版图渲染图
ls artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/render/
```

---

## 4. Signoff 检查 (DRC/LVS/XOR)

### 4.1 检查 DRC 结果

```bash
# 检查 Magic DRC
cat artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/reports/magic-drc/magic.drc

# 检查 KLayout DRC
cat artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/reports/klayout-drc/klayout.drc
```

### 4.2 检查 LVS 结果

```bash
# 检查 LVS 报告
cat artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/reports/lvs/lvs.rpt
```

### 4.3 检查 XOR 结果

```bash
# 检查 XOR 差异
cat artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/reports/xor/xor.rpt
```

### 4.4 检查天线违规

```bash
# 检查天线报告
cat artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/reports/antenna/antenna.rpt
```

---

## 5. KiCad PCB 输出

### 5.1 生成的 KiCad 文件

LibreLane 流程会自动生成 KiCad 文件，位于：
```
artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/kicad/
├── PicoRV32_BGA256.kicad_pro    # 项目文件
├── PicoRV32_BGA256.kicad_sch    # 原理图
├── PicoRV32_BGA256.kicad_pcb    # PCB 布局
├── PicoRV32.kicad_sym           # 符号库
├── PicoRV32_BGA256.kicad_mod    # 封装库
├── fp-lib-table                 # 封装库配置
└── sym-lib-table                # 符号库配置
```

### 5.2 打开 KiCad 项目

```bash
# 打开项目文件 (会自动加载原理图和 PCB)
kicad artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/kicad/PicoRV32_BGA256.kicad_pro
```

### 5.3 BGA-256 封装规格

- **封装类型**: BGA-256
- **焊球阵列**: 16×16
- **焊球间距**: 1.0mm
- **封装尺寸**: 17mm × 17mm
- **电源焊球**: 64 个 VPWR + 64 个 VGND
- **信号焊球**: 128 个

---

## 6. 仿真测试

### 6.1 运行仿真

```bash
cd ~/SiliconTrace/tests/simulation

# 需要安装 Icarus Verilog
sudo apt install iverilog

# 运行仿真
make sim

# 查看波形 (需要 GTKWave)
sudo apt install gtkwave
make wave
```

### 6.2 输出文件

| 文件 | 说明 | 查看方式 |
|------|------|---------|
| `tests/simulation/sim.vvp` | 编译后仿真文件 | - |
| `tests/simulation/dump.vcd` | 波形文件 | GTKWave |

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
cd ~/SiliconTrace

# 构建镜像
docker compose -f docker/docker-compose.yml build
```

### 7.3 运行 Docker 容器

```bash
# 启动 EDA 环境
docker compose -f docker/docker-compose.yml up -d

# 进入容器
docker exec -it silicontrace-eda bash

# 在容器内运行 PicoRV32
bash scripts/run_picorv32_librelane.sh sky130_picorv32
```

### 7.4 Docker 常用命令

```bash
# 查看运行中的容器
docker ps

# 停止容器
docker compose -f docker/docker-compose.yml down

# 查看日志
docker logs silicontrace-eda

# 进入容器
docker exec -it silicontrace-eda bash
```

---

## 8. AI 交互控制台

### 8.1 启动控制台

```bash
cd ~/SiliconTrace

# 安装依赖
pip3 install flask flask-cors

# 启动控制台
python3 frontend/app.py
```

### 8.2 访问控制台

打开浏览器访问: http://localhost:5000

### 8.3 可用命令

| 命令 | 说明 |
|------|------|
| `综合` / `synthesis` / `yosys` | 运行 Yosys 综合 |
| `pico` / `picorv32` | 运行 PicoRV32 LibreLane 流程 |
| `serv` | 运行 SERV LibreLane 流程 |
| `status` / `状态` | 查看项目状态 |
| `kicad` / `检查kicad` | 检查 KiCad 文件 |

### 8.4 API 接口

```bash
# 执行命令
curl -X POST http://localhost:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "综合"}'

# 获取状态
curl http://localhost:5000/api/status
```

---

## 9. 全流程一键运行

### 9.1 使用脚本

```bash
cd ~/SiliconTrace

# 运行 PicoRV32
bash scripts/run_picorv32_librelane.sh sky130_picorv32

# 运行 SERV
bash scripts/run_serv_librelane.sh sky130_test
```

### 9.2 使用 AI 控制台

1. 启动控制台: `python3 frontend/app.py`
2. 打开浏览器: http://localhost:5000
3. 输入命令: `pico` 或 `serv`

### 9.3 完整日志输出示例

```
========================================
  硅迹开源 - PicoRV32 LibreLane 流程
========================================

>>> 开始: RTL 综合 <<<
[10:00:00] [info] === 开始 Yosys 综合 ===
[10:00:01] [info] 读取 RTL 源码...
[10:00:45] [success] 综合完成!

>>> 开始: 后端流程 <<<
[10:01:00] [info] === 开始 LibreLane/OpenROAD 流程 ===
[10:01:01] [info] Floorplan...
[10:02:00] [info] Placement...
[10:03:00] [info] CTS...
[10:04:00] [info] Routing...
[10:05:00] [info] Signoff DRC/LVS...
[10:06:00] [success] 后端流程完成!

>>> 开始: KiCad 输出 <<<
[10:06:01] [info] 生成 KiCad 文件...
[10:06:05] [success] KiCad 文件生成完成!

========================================
  全流程完成!
========================================

输出文件:
- artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/gds/
- artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/kicad/
- artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/metrics.json
```

---

## 附录: 常见问题

### Q1: LibreLane 运行失败
**解决方案:** 检查 PDK 是否正确安装: `volare enable --pdk sky130`

### Q2: DRC 有违规
**解决方案:** 检查 `metrics.json` 中的 `magic__drc_error__count` 和 `klayout__drc_error__count`

### Q3: LVS 不匹配
**解决方案:** 检查 `metrics.json` 中的 `design__lvs_error__count`

### Q4: KiCad 文件打不开
**解决方案:** 确保使用 KiCad 7+，打开 `.kicad_pro` 文件而不是 `.kicad_mod` 文件

### Q5: 天线违规
**解决方案:** 在配置文件中调整 `RUN_ANTENNA_REPAIR: true` 和 `GRT_ANTENNA_REPAIR_ITERS`
