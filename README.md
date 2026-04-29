# 硅迹开源 (SiliconTrace Open)

> 一个中国大学生，不依赖任何商业软件License，仅凭开源工具和一台电脑，走完从芯片设计到板级验证的完整链路。

## 项目简介

硅迹开源是一个全开源数字IC设计工作室，致力于验证一条中国人可以零成本走通的芯片设计之路。

### 核心工具链

| 工具 | 用途 | 版本 |
|------|------|------|
| Yosys | 开源综合工具 | 0.64+ |
| iEDA | 国产开源数字后端平台 | Latest |
| KiCad | 开源PCB设计 | 6.0+ |
| SKY130 PDK | SkyWater 130nm 工艺 | sky130A |

### 设计流程

```
RTL (Verilog)
    ↓
Yosys 综合
    ↓
网表转换 (Python脚本)
    ↓
iEDA 后端实现
    ├─ 布局规划 (Floorplan)
    ├─ 布局 (Placement)
    ├─ 时钟树综合 (CTS)
    ├─ 布线 (Routing)
    └─ 时序分析 (STA)
    ↓
GDSII 输出
    ↓
KiCad 测试载板设计
    ↓
流片 + 测试验证
```

## 目录结构

```
SiliconTrace_Open/
├── rtl/                    # RTL源代码
│   ├── picorv32/          # RISC-V核心
│   └── common/            # 公共模块
├── synthesis/              # 综合相关
│   ├── synth.ys           # Yosys综合脚本
│   ├── constraints/       # 时序约束
│   └── results/           # 综合结果
├── backend/                # 后端实现
│   ├── floorplan/         # 布局规划
│   ├── placement/         # 布局
│   ├── cts/               # 时钟树
│   ├── routing/           # 布线
│   ├── sta/               # 时序分析
│   └── gdsii/             # GDSII输出
├── scripts/                # 自动化脚本
│   ├── yosys2ieda/        # 网表转换
│   ├── ieda_utils/        # iEDA工具
│   └── automation/        # 全流程脚本
├── kicad/                  # KiCad项目
│   ├── test_board/        # 测试载板
│   └── templates/         # 模板
├── docs/                   # 文档
│   ├── blog/              # 技术博客
│   └── tutorials/         # 教程
└── tests/                  # 测试
    ├── simulation/        # 仿真
    └── formal/            # 形式验证
```

## 快速开始

### 1. 环境配置

```bash
# 安装依赖
sudo apt install -y build-essential yosys kicad

# 安装 iEDA
git clone https://github.com/OSCC-Project/iEDA.git
cd iEDA && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# 安装 PDK
pip3 install volare
volare enable -p sky130
```

### 2. 运行综合

```bash
cd synthesis
bash run_synth.sh
```

### 3. 运行后端实现

```bash
cd scripts/automation
bash run_full_flow.sh
```

### 4. 查看结果

```bash
# 综合结果
ls synthesis/results/

# 后端结果
ls backend/routing/
ls backend/sta/
```

## 自动化脚本

### 网表转换
```bash
python3 scripts/yosys2ieda/convert_netlist.py \
    synthesis/results/picorv32_netlist.json \
    backend/converted
```

### 约束合并
```bash
python3 scripts/yosys2ieda/convert_constraints.py \
    output.sdc \
    constraint1.sdc \
    constraint2.sdc
```

### 报告生成
```bash
python3 scripts/ieda_utils/generate_report.py \
    backend/sta/sta_setup.rpt \
    backend/sta/power.rpt \
    report.txt
```

## 设计案例

### PicoRV32 RISC-V 核

- **工艺**: SKY130 130nm
- **频率**: 100MHz
- **面积**: 500μm × 500μm
- **状态**: 开发中

## 参与贡献

欢迎提交 Issue 和 Pull Request！

### 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 联系方式

- GitHub: [SiliconTrace_Open](https://github.com/yourusername/SiliconTrace_Open)
- B站: 硅迹开源
- 知乎: 硅迹开源

## 致谢

- [YosysHQ](https://github.com/YosysHQ) - 开源综合工具
- [iEDA](https://github.com/OSCC-Project/iEDA) - 国产开源数字后端平台
- [KiCad](https://www.kicad.org/) - 开源PCB设计工具
- [SkyWater PDK](https://github.com/google/skywater-pdk) - 130nm工艺设计套件
