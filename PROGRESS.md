# 硅迹开源 - 进度总结

## 一、环境配置（已完成）

### 1.1 系统依赖
- ✅ apt 源修复（bionic → jammy，阿里云镜像）
- ✅ 系统依赖安装（build-essential, cmake, boost, eigen3, glog, gflags, tbb, gtest, libgmp 等）

### 1.2 工具链安装
- ✅ Yosys v0.64+172（源码编译，`/usr/local/bin/yosys`）
- ✅ iEDA（源码编译，二进制位置 `~/iEDA/scripts/design/sky130_gcd/iEDA`）
- ✅ SKY130 PDK（volare 安装，`~/.volare/sky130A`）
- ✅ KiCad v6.0.2（apt 安装）
- ✅ Volare v0.20.6（pip 安装）
- ✅ Rust/Cargo v1.95.0（iEDA 编译依赖）

### 1.3 环境变量
- ✅ `~/.eda_env` 配置文件创建
- ✅ 已添加到 `~/.bashrc`

```bash
# ~/.eda_env 内容
export PDK_ROOT="$HOME/.volare"
export PDK=sky130A
export YOSYS_ROOT="$HOME/yosys"
export IEDA_ROOT="$HOME/iEDA"
export IEDA_BIN="$HOME/iEDA/scripts/design/sky130_gcd/iEDA"
export PATH="$HOME/.cargo/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PATH="$IEDA_ROOT/scripts/design/sky130_gcd:$PATH"
export OPC_ROOT="$HOME/OPC_plan"
```

---

## 二、SiliconTrace_Open 项目创建（已完成）

### 2.1 项目结构
```
~/SiliconTrace_Open/
├── rtl/picorv32/           # ✅ PicoRV32 RTL 源码（3049行）
├── synthesis/              # ✅ Yosys 综合
│   ├── synth.ys           # ✅ 综合脚本
│   ├── constraints/       # ✅ SDC 约束
│   └── run_synth.sh       # ✅ 综合运行脚本
├── backend/                # ✅ iEDA 后端
│   ├── floorplan/         # ✅ 布局规划脚本
│   ├── placement/         # ✅ 布局脚本
│   ├── cts/               # ✅ 时钟树综合脚本
│   ├── routing/           # ✅ 布线脚本
│   └── sta/               # ✅ 时序分析脚本
├── scripts/                # ✅ 自动化脚本
│   ├── yosys2ieda/        # ✅ 网表/约束转换
│   ├── ieda_utils/        # ✅ 报告生成
│   └── automation/        # ✅ 全流程脚本 + 清理脚本
├── kicad/test_board/       # ✅ KiCad 项目模板
├── README.md               # ✅ 项目说明
├── .gitignore              # ✅ Git 忽略规则
├── .github/workflows/      # ✅ CI 配置
└── docs/                   # 空目录，待填充
```

### 2.2 自动化脚本清单
| 脚本 | 功能 | 状态 |
|------|------|------|
| `scripts/automation/run_full_flow.sh` | RTL→GDSII 一键全流程 | ✅ |
| `scripts/automation/clean.sh` | 清理生成文件 | ✅ |
| `scripts/yosys2ieda/convert_netlist.py` | Yosys JSON 网表 → iEDA 格式 | ✅ |
| `scripts/yosys2ieda/convert_constraints.py` | SDC 约束合并/转换 | ✅ |
| `scripts/ieda_utils/generate_report.py` | STA/功耗报告解析 | ✅ |

---

## 三、未完成 / 待继续

### 3.1 功能验证（未跑通）
- ❌ 未实际运行综合（`bash synthesis/run_synth.sh`）
- ❌ 未实际运行后端流程（`bash scripts/automation/run_full_flow.sh`）
- ❌ iEDA 脚本可能需要根据实际 iEDA 版本调整 Tcl 命令语法
- ❌ 网表转换脚本未测试

### 3.2 KiCad 测试载板（只有空模板）
- ❌ 缺少 PicoRV32 的原理图符号（Symbol）
- ❌ 缺少封装（Footprint）
- ❌ 缺少实际的原理图设计
- ❌ 缺少四层 PCB Layout

### 3.3 文档与博客（目录为空）
- ❌ `docs/blog/` 无内容
- ❌ `docs/tutorials/` 无内容
- ❌ 缺少「从 RTL 到 GDSII」完整教程

### 3.4 测试（目录为空）
- ❌ `tests/simulation/` 无仿真测试
- ❌ `tests/formal/` 无形式验证

### 3.5 GitHub 仓库
- ❌ 未初始化 git（`git init`）
- ❌ 未创建首次 commit
- ❌ 未推送到远程仓库

---

## 四、下一步操作建议

```bash
# 1. 进入项目目录
cd ~/SiliconTrace_Open

# 2. 测试综合
cd synthesis && bash run_synth.sh

# 3. 测试全流程（综合 + 后端）
cd scripts/automation && bash run_full_flow.sh

# 4. 根据报错调整 iEDA Tcl 脚本语法

# 5. 初始化 git
git init && git add . && git commit -m "init: 硅迹开源项目初始化"

# 6. 创建远程仓库并推送
gh repo create SiliconTrace_Open --public --source=. --push
```

---

## 五、关键文件位置

| 文件 | 路径 |
|------|------|
| PicoRV32 RTL | `~/SiliconTrace_Open/rtl/picorv32/picorv32.v` |
| 综合脚本 | `~/SiliconTrace_Open/synthesis/synth.ys` |
| SDC 约束 | `~/SiliconTrace_Open/synthesis/constraints/picorv32.sdc` |
| 全流程脚本 | `~/SiliconTrace_Open/scripts/automation/run_full_flow.sh` |
| 网表转换 | `~/SiliconTrace_Open/scripts/yosys2ieda/convert_netlist.py` |
| 环境变量 | `~/.eda_env` |
| iEDA 二进制 | `~/iEDA/scripts/design/sky130_gcd/iEDA` |
| SKY130 PDK | `~/.volare/sky130A/` |
