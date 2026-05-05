# 硅迹开源 (SiliconTrace Open)

> 一个中国大学生，不依赖任何商业软件License，仅凭开源工具和一台电脑，走完从芯片设计到板级验证的完整链路。

---

## 项目愿景

本项目是为了推动开源运动而进行的一个尝试，希望能够通过引入AI这种方式，让IC设计的门槛降低，让学习IC设计的门槛降低，并且也推动开源事业的发展。

我们相信：芯片设计不应该是少数人的特权。借助开源工具链和AI辅助，任何人都可以在一台普通的电脑上，完成从RTL代码到物理版图的完整芯片设计流程。

---

## 项目架构

```mermaid
graph TB
    subgraph 用户界面层
        A[AI 交互控制台<br/>Web 前端]
    end

    subgraph 设计流程层
        B[RTL 设计<br/>Verilog HDL]
        C[Yosys 综合<br/>RTL→门级网表]
        D[LibreLane/OpenROAD 后端<br/>布局布线]
        E[GDSII 输出<br/>物理版图]
        F[KiCad 载板<br/>PCB 设计]
    end

    subgraph 工具链层
        G[Yosys 0.64+]
        H[LibreLane 3.x]
        I[KiCad 7.0+]
        J[SKY130 PDK]
    end

    subgraph 自动化层
        K[Shell 脚本<br/>全流程]
        L[Python 脚本<br/>KiCad 生成]
    end

    A -->|发送命令| B
    B --> C --> D --> E --> F
    A -->|实时日志| G
    A -->|实时日志| H
    A -->|实时日志| I
    K --> B
    L --> F
```

```mermaid
graph LR
    subgraph RTL综合
        R1[读取 Verilog] --> R2[逻辑优化<br/>proc/opt/flatten]
        R2 --> R3[寄存器展开<br/>memory_map]
        R3 --> R4[技术映射<br/>techmap/abc]
        R4 --> R5[输出网表<br/>.v + .json]
    end

    subgraph 后端流程-LibreLane/OpenROAD
        P1[Floorplan] --> P2[Global Placement]
        P2 --> P3[Detailed Placement]
        P3 --> P4[CTS]
        P4 --> P5[Global Routing]
        P5 --> P6[Detailed Routing]
        P6 --> P7[Signoff DRC/LVS]
        P7 --> P8[GDSII 版图输出]
    end

    R5 --> P1
```

---

## 详细目录结构

```
SiliconTrace/
│
├── rtl/                              # RTL 源代码
│   ├── picorv32/                     # PicoRV32 RISC-V 处理器核心
│   │   └── picorv32.v                # Verilog 源码 (3049行)
│   └── serv/                         # SERV 串行 RISC-V 处理器
│
├── synthesis/                        # Yosys 综合
│   ├── synth.ys                      # 综合脚本模板
│   ├── run_synth.sh                  # 综合运行脚本
│   └── constraints/                  # SDC 时序约束
│       ├── picorv32.sdc
│       └── serv_synth_wrapper.sdc
│
├── backend/                          # 后端配置
│   └── config/                       # LibreLane 配置文件
│       └── picorv32_librelane_sky130.yaml  # PicoRV32 配置
│
├── scripts/                          # 自动化脚本
│   ├── run_picorv32_librelane.sh     # PicoRV32 LibreLane 运行脚本
│   ├── run_serv_librelane.sh         # SERV LibreLane 运行脚本
│   └── automation/                   # 全流程脚本
│       ├── run_full_flow.sh          # RTL→GDSII 一键运行
│       └── clean.sh                  # 清理生成文件
│
├── artifacts/                        # 生成输出目录 (gitignored)
│   └── librelane/                    # LibreLane 运行结果
│       ├── picorv32_sky130/          # PicoRV32 设计结果
│       │   └── runs/                 # 运行目录
│       │       └── sky130_picorv32_fullfix13/  # 最佳运行
│       │           └── final/        # 最终输出
│       │               ├── gds/      # GDSII 文件
│       │               ├── kicad/    # KiCad 文件
│       │               └── metrics.json  # 指标报告
│       └── serv_sky130/              # SERV 设计结果
│
├── kicad/                            # KiCad PCB 设计
│   ├── test_board/                   # 测试载板
│   │   ├── test_board.kicad_pro      # 项目文件
│   │   ├── test_board.kicad_sch      # 原理图
│   │   └── test_board.kicad_pcb      # PCB Layout
│   ├── symbols/                      # 原理图符号库
│   └── footprints/                   # 封装库
│
├── frontend/                         # AI 交互控制台
│   ├── app.py                        # Flask 后端
│   └── templates/                    # Web 前端模板
│
├── docker/                           # Docker 环境
│   ├── Dockerfile                    # EDA 工具链镜像
│   └── docker-compose.yml            # Docker Compose 配置
│
├── tests/                            # 测试
│   ├── simulation/                   # 仿真测试
│   └── formal/                       # 形式验证
│
├── docs/                             # 文档
│   └── COMMANDS.md                   # 完整命令手册
│
├── README.md                         # 本文件
├── USAGE.md                          # 使用说明
├── PROGRESS.md                       # 进度记录
└── .gitignore
```

---

## 核心工具链

| 工具 | 用途 | 版本 | 开源协议 |
|------|------|------|----------|
| **Yosys** | RTL 综合 (Verilog → 门级网表) | 0.64+ | ISC |
| **LibreLane** | 开源数字后端流程 (基于 OpenROAD) | 3.x | Apache 2.0 |
| **OpenROAD** | 开源 EDA 平台 (通过 LibreLane 调用) | Latest | BSD |
| **Magic** | 版图编辑和 DRC 检查 | Latest | MIT |
| **KLayout** | 版图查看和 DRC 检查 | Latest | GPL |
| **Netgen** | LVS 网表对比 | Latest | BSD |
| **KiCad** | 开源 PCB 设计 | 7.0+ | GPL |
| **SKY130 PDK** | SkyWater 130nm 工艺设计套件 | sky130A | Apache 2.0 |
| **Volare** | PDK 版本管理工具 | 0.20+ | MIT |

---

## 快速开始

### 方式一：直接构建 (推荐学习)

适合希望深入了解每一步流程的学习者。

#### 1. 系统依赖安装

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

#### 2. 安装 Yosys

```bash
# 方法 1: apt 安装 (推荐)
sudo apt install -y yosys

# 方法 2: 源码编译
git clone https://github.com/YosysHQ/yosys.git
cd yosys && make -j$(nproc) && sudo make install
```

#### 3. 安装 SKY130 PDK

```bash
volare enable --pdk sky130
```

#### 4. 运行 PicoRV32 完整流程

```bash
cd ~/SiliconTrace

# 运行 PicoRV32 LibreLane 流程
bash scripts/run_picorv32_librelane.sh sky130_picorv32

# 查看结果
ls artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/
```

#### 5. 查看生成的 KiCad 文件

```bash
# 打开 KiCad 项目
kicad artifacts/librelane/picorv32_sky130/runs/sky130_picorv32/final/kicad/PicoRV32_BGA256.kicad_pro
```

#### 6. 使用 AI 交互控制台

```bash
pip3 install flask flask-cors
python3 frontend/app.py
# 浏览器访问: http://localhost:5000
```

---

### 方式二：Docker 构建 (推荐部署)

适合希望快速搭建环境或在多台机器上复现的用户。

#### 1. 安装 Docker

```bash
# 安装 Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 添加 Docker GPG 密钥和源
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 将用户添加到 docker 组
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. 构建 Docker 镜像

```bash
cd ~/SiliconTrace

# 构建包含所有 EDA 工具的镜像
docker compose -f docker/docker-compose.yml build
```

#### 3. 启动环境

```bash
# 启动 EDA 环境 + AI 前端
docker compose -f docker/docker-compose.yml up -d

# 进入 EDA 容器
docker exec -it silicontrace-eda bash

# 在容器内运行 PicoRV32
bash scripts/run_picorv32_librelane.sh sky130_picorv32
```

---

## AI 交互控制台

硅迹开源提供了一个 Web 界面，让您可以通过交互式命令控制整个设计流程。

### 功能特性

- **流程可视化**: 实时显示 7 个设计步骤的状态 (综合 → Floorplan → Placement → CTS → Routing → STA → GDSII)
- **工具链检测**: 自动检测 Yosys、iEDA、KiCad、PDK 等工具的安装状态
- **实时日志**: 查看每一步的详细执行日志
- **设计切换**: 支持多个 RTL 设计之间的切换和管理
- **文件导入**: 支持导入自定义 RTL 设计、芯片封装、原理图符号
- **生成文件浏览**: 直接在前端查看后端生成的网表、DEF、GDSII 等文件
- **MCP 接口**: 提供程序化上传 API，支持 AI 代理调用

### 启动方式

```bash
pip3 install flask flask-cors
python3 frontend/app.py
```

浏览器访问: http://localhost:5000

### 可用命令

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

### MCP 上传接口

```bash
# RTL 设计上传
curl -X POST http://localhost:5000/api/upload/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "import",
    "type": "rtl",
    "filename": "my_design.v",
    "content": "module my_design(...); endmodule",
    "encoding": "text",
    "design_name": "my_design"
  }'

# 芯片封装上传
curl -X POST http://localhost:5000/api/upload/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "import",
    "type": "footprint",
    "filename": "my_chip.kicad_mod",
    "content": "(module my_chip ...)",
    "encoding": "text"
  }'
```

---

## 输出文件说明

| 阶段 | 输出文件 | 查看方式 |
|------|----------|----------|
| 综合 | `artifacts/synthesis/picorv32_netlist.v` | Vim / VS Code |
| GDSII | `artifacts/librelane/picorv32_sky130/runs/*/final/gds/` | KLayout |
| DRC 报告 | `artifacts/librelane/picorv32_sky130/runs/*/final/metrics.json` | Vim / VS Code |
| KiCad PCB | `artifacts/librelane/picorv32_sky130/runs/*/final/kicad/PicoRV32_BGA256.kicad_pcb` | KiCad |
| KiCad 原理图 | `artifacts/librelane/picorv32_sky130/runs/*/final/kicad/PicoRV32_BGA256.kicad_sch` | KiCad |
| 渲染图 | `artifacts/librelane/picorv32_sky130/runs/*/final/render/` | 图片查看器 |

---

## 设计案例

### PicoRV32 RISC-V 处理器核心

- **工艺**: SKY130 130nm
- **设计规模**: ~3000 行 Verilog
- **Die 面积**: 1200μm × 1200μm
- **标准单元库**: sky130_fd_sc_hd (高密度)
- **封装**: BGA-256 (17mm × 17mm, 1.0mm pitch)
- **Signoff 状态**: DRC=0, LVS=0, XOR=0

### SERV 串行 RISC-V 处理器核心

- **工艺**: SKY130 130nm
- **设计规模**: 极小 (串行架构)
- **Die 面积**: 600μm × 600μm
- **标准单元库**: sky130_fd_sc_hd (高密度)
- **Signoff 状态**: DRC=0, LVS=0, XOR=0

---

## 参与贡献

欢迎提交 Issue 和 Pull Request！

### 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 致谢

- [YosysHQ](https://github.com/YosysHQ) - 开源综合工具
- [LibreLane](https://github.com/efabless/librelane) - 开源数字后端流程
- [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) - 开源 EDA 平台
- [KiCad](https://www.kicad.org/) - 开源 PCB 设计工具
- [SkyWater PDK](https://github.com/google/skywater-pdk) - 130nm 工艺设计套件
- [PicoRV32](https://github.com/cliffordwolf/picorv32) - RISC-V 处理器核心
- [SERV](https://github.com/olofk/serv) - 串行 RISC-V 处理器核心

---

## 联系方式

- GitHub: [SiliconTrace_Open](https://github.com/ForBloodB/SiliconTrace_Open)
- B站: 硅迹开源
- 知乎: 硅迹开源
