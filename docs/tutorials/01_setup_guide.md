# SiliconTrace Open 环境搭建指南

> 本教程将指导你从零开始搭建 SiliconTrace Open 项目所需的完整开发环境。涵盖开源 EDA 工具链的编译安装、PDK 的配置以及环境验证。

## 目录

- [1. 系统要求](#1-系统要求)
- [2. 安装基础依赖](#2-安装基础依赖)
- [3. 从源码编译 Yosys](#3-从源码编译-yosys)
- [4. 从源码编译 iEDA](#4-从源码编译-ieda)
- [5. 安装 SKY130 PDK](#5-安装-sky130-pdk)
- [6. 安装 KiCad](#6-安装-kicad)
- [7. 配置环境变量](#7-配置环境变量)
- [8. 验证安装](#8-验证安装)
- [9. 常见问题](#9-常见问题)

---

## 1. 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Ubuntu 22.04 LTS | Ubuntu 22.04 / 24.04 LTS |
| CPU | 4 核 | 8 核以上 |
| 内存 | 8 GB | 16 GB 以上 |
| 磁盘空间 | 50 GB 可用 | 100 GB 以上（SSD 推荐） |
| 网络 | 需要互联网连接 | 稳定的网络连接 |

> **注意**: 本教程基于 Ubuntu 22.04 LTS 编写。其他 Linux 发行版（如 Debian、Fedora）步骤类似，但包管理器命令需要相应调整。

---

## 2. 安装基础依赖

首先更新系统并安装编译所需的工具链和库：

```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 安装编译工具链
sudo apt install -y \
    build-essential \
    clang \
    cmake \
    ninja-build \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    tcl-dev \
    libreadline-dev \
    libffi-dev \
    libboost-all-dev \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libssl-dev \
    pkg-config \
    autoconf \
    automake \
    libtool \
    bison \
    flex \
    gawk \
    graphviz \
    xdot \
    libgraphviz-dev \
    protobuf-compiler \
    libprotobuf-dev

# 安装 Python 常用包
pip3 install --user \
    numpy \
    matplotlib \
    pandas \
    pyyaml \
    protobuf \
    grpcio
```

---

## 3. 从源码编译 Yosys

Yosys 是开源综合工具，负责将 Verilog RTL 代码转换为门级网表。

### 3.1 获取源码

```bash
# 创建工作目录
mkdir -p ~/eda_tools && cd ~/eda_tools

# 克隆 Yosys 仓库
git clone https://github.com/YosysHQ/yosys.git
cd yosys

# 切换到稳定版本（推荐）
git checkout yosys-0.38
```

### 3.2 编译安装

```bash
# 配置编译选项
make config-clang

# 编译（使用多核加速，-j 后的数字为核心数）
make -j$(nproc)

# 安装到系统目录
sudo make install

# 验证安装
yosys -V
```

预期输出类似：
```
Yosys 0.38 (git hash xxxxxxx, clang 14.0.0 -fPIC -Os)
```

### 3.3 安装 Yosys 插件（可选）

```bash
# 安装 sby（形式验证前端）
cd ~/eda_tools
git clone https://github.com/YosysHQ/sby.git
cd sby
sudo make install

# 安装 eqy（等价性检查）
cd ~/eda_tools
git clone https://github.com/YosysHQ/eqy.git
cd eqy
sudo make install
```

---

## 4. 从源码编译 iEDA

iEDA 是由中科院计算所开发的国产开源数字后端 EDA 平台，支持从 Netlist 到 GDSII 的完整后端流程。

### 4.1 获取源码

```bash
cd ~/eda_tools

# 克隆 iEDA 仓库
git clone https://github.com/OSCC-Project/iEDA.git
cd iEDA

# 切换到稳定分支
git checkout main
```

### 4.2 编译安装

```bash
# iEDA 使用 CMake 构建系统
mkdir build && cd build

# 配置编译选项
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DBUILD_TESTS=OFF

# 编译
cmake --build . -j$(nproc)

# 安装
sudo cmake --install .
```

### 4.3 验证 iEDA 安装

```bash
# 检查 iEDA 可执行文件
ls /usr/local/bin/ieda*

# 或者直接使用源码目录中的可执行文件
ls ~/eda_tools/iEDA/build/bin/
```

> **注意**: iEDA 目前仍在快速迭代中，不同版本的 API 和配置文件格式可能有所不同。建议参考项目 README 中的最新编译说明。

### 4.4 iEDA 子模块说明

iEDA 包含多个子模块，每个模块负责后端流程的不同阶段：

| 子模块 | 功能 | 说明 |
|--------|------|------|
| iPL | Placement（布局） | 全局布局 + 详细布局 |
| iCTS | Clock Tree Synthesis（时钟树综合） | 时钟树构建与优化 |
| iRT | Routing（布线） | 全局布线 + 详细布线 |
| iSTA | Static Timing Analysis（静态时序分析） | 时序分析与报告 |
| iDRC | Design Rule Check（设计规则检查） | 物理验证 |
| iTO | Timing Optimization（时序优化） | 后端时序优化 |

---

## 5. 安装 SKY130 PDK

SKY130 是 SkyWater 130nm 工艺的开源 PDK（Process Design Kit），是目前最成熟的开源工艺库。

### 5.1 使用 volare 安装

volare 是 OpenLane 团队开发的 PDK 管理工具，可以方便地安装和管理开源 PDK。

```bash
# 安装 volare
pip3 install --user volare

# 验证 volare 安装
volare --version

# 查看可用的 SKY130 PDK 版本
volare enable_versions --pdk sky130

# 安装推荐版本的 SKY130 PDK
volare enable --pdk sky130 --pdk-root ~/pdk 0.0.0.20240115
```

> **注意**: 版本号可能会更新，请使用 `volare enable_versions --pdk sky130` 查看最新可用版本。

### 5.2 PDK 目录结构

安装完成后，PDK 的目录结构如下：

```
~/pdk/
└── sky130A/
    ├── libs.ref/          # 参考库（综合、仿真用）
    │   ├── sky130_fd_sc_hd/    # 标准单元库（高密度）
    │   │   ├── lib/            # Liberty 时序库
    │   │   ├── lef/            # LEF 物理库
    │   │   ├── verilog/        # Verilog 行为模型
    │   │   └── spice/          # SPICE 网表
    │   ├── sky130_fd_sc_hs/    # 标准单元库（高速）
    │   ├── sky130_fd_sc_ms/    # 标准单元库（中速）
    │   ├── sky130_fd_sc_ls/    # 标准单元库（低速）
    │   └── sky130_fd_sc_lp/    # 标准单元库（低功耗）
    └── libs.tech/         # 工艺库（后端用）
        ├── klayout/       # KLayout 配置
        ├── openlane/      # OpenLane 配置
        └── qflow/         # Qflow 配置
```

### 5.3 标准单元库版本选择

SKY130 提供了多个标准单元库变体，本项目使用 `sky130_fd_sc_hd`（高密度）版本：

- **sky130_fd_sc_hd**: 高密度单元，面积最小，适合大多数设计
- **sky130_fd_sc_hs**: 高速单元，驱动能力强，但面积较大
- **sky130_fd_sc_ms**: 中速单元，速度与面积的折中
- **sky130_fd_sc_ls**: 低速单元，功耗较低
- **sky130_fd_sc_lp**: 低功耗单元，适合低功耗设计

---

## 6. 安装 KiCad

KiCad 是开源的 PCB 设计工具，用于设计测试板。

### 6.1 安装 KiCad 8.0

```bash
# 添加 KiCad 官方 PPA
sudo add-apt-repository ppa:kicad/kicad-8.0-releases
sudo apt update

# 安装 KiCad
sudo apt install -y kicad

# 安装额外的符号库和封装库（可选）
sudo apt install -y \
    kicad-symbols \
    kicad-footprints \
    kicad-packages3d \
    kicad-templates
```

### 6.2 验证安装

```bash
# 启动 KiCad
kicad

# 检查版本
kicad-cli version
```

---

## 7. 配置环境变量

为了方便使用各工具，我们需要配置环境变量文件 `~/.eda_env`。

### 7.1 创建环境变量文件

```bash
cat > ~/.eda_env << 'EOF'
# ============================================
# SiliconTrace Open EDA 环境变量配置
# ============================================

# ---- PDK 配置 ----
export PDK_ROOT="$HOME/pdk"
export PDK="sky130A"
export PDK_PATH="$PDK_ROOT/$PDK"

# ---- 标准单元库路径 ----
export SC_LIB="$PDK_PATH/libs.ref/sky130_fd_sc_hd"
export SC_LEF="$SC_LIB/lef/sky130_fd_sc_hd.lef"
export SC_LIBERTY="$SC_LIB/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
export SC_VERILOG="$SC_LIB/verilog/primitives.v"

# ---- iEDA 配置 ----
export IEDA_ROOT="$HOME/eda_tools/iEDA"
export IEDA_BIN="$IEDA_ROOT/build/bin"

# ---- Yosys 配置 ----
export YOSYS_DAT_DIR="/usr/local/share/yosys"

# ---- 项目路径 ----
export SILICONTRACE_ROOT="$HOME/SiliconTrace_Open"
export SILICONTRACE_RTL="$SILICONTRACE_ROOT/rtl"
export SILICONTRACE_SYNTH="$SILICONTRACE_ROOT/synth"
export SILICONTRACE_BACKEND="$SILICONTRACE_ROOT/backend"
export SILICONTRACE_PCB="$SILICONTRACE_ROOT/pcb"

# ---- 工具路径 ----
export PATH="$IEDA_BIN:$PATH"

# ---- 输出目录 ----
export RESULTS_DIR="$SILICONTRACE_ROOT/results"
export LOGS_DIR="$SILICONTRACE_ROOT/logs"
EOF
```

### 7.2 加载环境变量

```bash
# 将环境变量加载添加到 .bashrc
echo '' >> ~/.bashrc
echo '# 加载 EDA 环境变量' >> ~/.bashrc
echo '[ -f ~/.eda_env ] && source ~/.eda_env' >> ~/.bashrc

# 立即加载
source ~/.eda_env
```

### 7.3 环境变量说明

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `PDK_ROOT` | PDK 根目录 | `~/pdk` |
| `PDK` | PDK 名称 | `sky130A` |
| `SC_LIB` | 标准单元库根目录 | `~/pdk/sky130A/libs.ref/sky130_fd_sc_hd` |
| `SC_LEF` | 标准单元 LEF 文件 | `~/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef` |
| `SC_LIBERTY` | 标准单元 Liberty 文件 | `~/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib` |
| `IEDA_ROOT` | iEDA 源码根目录 | `~/eda_tools/iEDA` |
| `IEDA_BIN` | iEDA 可执行文件目录 | `~/eda_tools/iEDA/build/bin` |

---

## 8. 验证安装

### 8.1 创建验证脚本

```bash
cat > ~/verify_eda_setup.sh << 'SCRIPT'
#!/bin/bash

echo "=========================================="
echo "  SiliconTrace Open 环境验证"
echo "=========================================="

# 加载环境变量
source ~/.eda_env 2>/dev/null

PASS=0
FAIL=0

check_tool() {
    local name=$1
    local cmd=$2
    if eval "$cmd" &>/dev/null; then
        echo "[PASS] $name"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] $name - 未找到"
        FAIL=$((FAIL + 1))
    fi
}

check_file() {
    local name=$1
    local path=$2
    if [ -f "$path" ]; then
        echo "[PASS] $name: $path"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] $name: $path 不存在"
        FAIL=$((FAIL + 1))
    fi
}

check_dir() {
    local name=$1
    local path=$2
    if [ -d "$path" ]; then
        echo "[PASS] $name: $path"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] $name: $path 不存在"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "--- 工具检查 ---"
check_tool "Yosys" "yosys -V"
check_tool "iEDA" "ls $IEDA_BIN/ieda*"
check_tool "KiCad" "kicad-cli version"
check_tool "volare" "volare --version"

echo ""
echo "--- PDK 检查 ---"
check_dir "PDK 根目录" "$PDK_PATH"
check_dir "标准单元库 (HD)" "$SC_LIB"
check_file "LEF 文件" "$SC_LEF"
check_file "Liberty 文件" "$SC_LIBERTY"
check_dir "Verilog 行为模型" "$SC_LIB/verilog"

echo ""
echo "--- 环境变量检查 ---"
for var in PDK_ROOT PDK SC_LIB SC_LEF SC_LIBERTY IEDA_ROOT IEDA_BIN SILICONTRACE_ROOT; do
    if [ -n "${!var}" ]; then
        echo "[PASS] $var=${!var}"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] $var 未设置"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "=========================================="
echo "  结果: $PASS 通过, $FAIL 失败"
echo "=========================================="

if [ $FAIL -gt 0 ]; then
    echo "请检查失败项并重新配置。"
    exit 1
else
    echo "所有检查通过！环境配置正确。"
    exit 0
fi
SCRIPT

chmod +x ~/verify_eda_setup.sh
```

### 8.2 运行验证

```bash
~/verify_eda_setup.sh
```

预期输出：
```
==========================================
  SiliconTrace Open 环境验证
==========================================

--- 工具检查 ---
[PASS] Yosys
[PASS] iEDA
[PASS] KiCad
[PASS] volare

--- PDK 检查 ---
[PASS] PDK 根目录: /home/user/pdk/sky130A
[PASS] 标准单元库 (HD): /home/user/pdk/sky130A/libs.ref/sky130_fd_sc_hd
[PASS] LEF 文件: /home/user/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
[PASS] Liberty 文件: /home/user/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
[PASS] Verilog 行为模型: /home/user/pdk/sky130A/libs.ref/sky130_fd_sc_hd/verilog

--- 环境变量检查 ---
[PASS] PDK_ROOT=/home/user/pdk
[PASS] PDK=sky130A
[PASS] SC_LIB=...
[PASS] SC_LEF=...
[PASS] SC_LIBERTY=...
[PASS] IEDA_ROOT=...
[PASS] IEDA_BIN=...
[PASS] SILICONTRACE_ROOT=...

==========================================
  结果: 16 通过, 0 失败
==========================================
所有检查通过！环境配置正确。
```

---

## 9. 常见问题

### Q1: Yosys 编译时报错 "tcl.h not found"

```bash
# 安装 Tcl 开发包
sudo apt install -y tcl-dev

# 如果仍然找不到，手动指定路径
make config-clang
make TCL_INCLUDE=/usr/include/tcl8.6 -j$(nproc)
```

### Q2: volare 下载 PDK 超时

```bash
# 使用代理（如果需要）
export https_proxy=http://your_proxy:port
export http_proxy=http://your_proxy:port

# 或手动下载 PDK 后解压
mkdir -p ~/pdk/sky130A
# 从 GitHub Releases 手动下载并解压到 ~/pdk/sky130A/
```

### Q3: iEDA 编译时 CMake 版本过低

```bash
# 安装最新版本的 CMake
pip3 install --user cmake --upgrade

# 或从源码编译
cd /tmp
wget https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1.tar.gz
tar xzf cmake-3.28.1.tar.gz
cd cmake-3.28.1
./bootstrap && make -j$(nproc) && sudo make install
```

### Q4: 内存不足导致编译失败

```bash
# 减少并行编译数
make -j2  # 而不是 -j$(nproc)

# 或添加交换空间
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Q5: Liberty 文件有多个 corner，应该选哪个？

SKY130 的 Liberty 文件包含多个工艺角（corner），推荐使用：

- **综合阶段**: `sky130_fd_sc_hd__tt_025C_1v80.lib`（典型工艺角，25°C，1.8V）
- **时序签核**: 同时使用 fast corner 和 slow corner 进行分析
  - Fast: `sky130_fd_sc_hd__ff_n40C_1v95.lib`
  - Slow: `sky130_fd_sc_hd__ss_100C_1v60.lib`

---

> **下一步**: 环境搭建完成后，请继续阅读 [02_synthesis_guide.md](./02_synthesis_guide.md) 学习如何使用 Yosys 进行 RTL 综合。
