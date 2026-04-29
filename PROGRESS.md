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

---

## 二、SiliconTrace_Open 项目创建（已完成）

### 2.1 项目结构
```
~/SiliconTrace_Open/
├── rtl/picorv32/           # ✅ PicoRV32 RTL 源码（3049行）
├── synthesis/              # ✅ Yosys 综合
│   ├── synth.ys           # ✅ 综合脚本（含 memory_map）
│   ├── constraints/       # ✅ SDC 约束
│   └── run_synth.sh       # ✅ 综合运行脚本（含网表修复）
├── backend/                # ✅ iEDA 后端
│   ├── config/            # ✅ iEDA 配置文件（HD 单元库）
│   ├── tcl/               # ✅ iEDA Tcl 脚本
│   ├── run_ieda.sh        # ✅ 后端全流程脚本
│   └── *.tcl              # ✅ 原始脚本（参考用）
├── scripts/                # ✅ 自动化脚本
│   ├── yosys2ieda/        # ✅ 网表/约束转换 + 修复
│   ├── ieda_utils/        # ✅ 报告生成
│   └── automation/        # ✅ 全流程脚本 + 清理脚本
├── kicad/test_board/       # ✅ KiCad 项目
│   ├── test_board.kicad_pro  # ✅ 项目文件
│   ├── test_board.kicad_sch  # ✅ 原理图
│   └── test_board.kicad_pcb  # ✅ 四层 PCB Layout
├── kicad/symbols/          # ✅ 原理图符号库
│   └── picorv32.kicad_sym    # ✅ PicoRV32 符号
├── kicad/footprints/       # ✅ 封装库
│   └── QFN-48_7x7mm_P0.5mm.kicad_mod  # ✅ QFN-48 封装
├── docs/                   # ✅ 文档
│   ├── blog/              # ✅ 技术博客（2篇）
│   └── tutorials/         # ✅ 教程（4篇）
├── tests/                  # ✅ 测试
│   ├── simulation/        # ✅ 仿真测试平台
│   └── formal/            # ✅ 形式验证配置
├── README.md               # ✅ 项目说明
├── .gitignore              # ✅ Git 忽略规则
├── .github/workflows/      # ✅ CI 配置
└── plan.md                 # ✅ 项目规划
```

### 2.2 自动化脚本清单
| 脚本 | 功能 | 状态 |
|------|------|------|
| `scripts/automation/run_full_flow.sh` | RTL→GDSII 一键全流程 | ✅ |
| `scripts/automation/clean.sh` | 清理生成文件 | ✅ |
| `scripts/yosys2ieda/convert_netlist.py` | Yosys JSON 网表 → iEDA 格式 | ✅ |
| `scripts/yosys2ieda/convert_constraints.py` | SDC 约束合并/转换 | ✅ |
| `scripts/yosys2ieda/fix_netlist.py` | 修复网表中复杂拼接赋值 | ✅ |
| `scripts/ieda_utils/generate_report.py` | STA/功耗报告解析 | ✅ |
| `backend/run_ieda.sh` | iEDA 后端全流程 | ✅ |

---

## 三、功能验证状态

### 3.1 Yosys 综合（✅ 已验证）
- ✅ `bash synthesis/run_synth.sh` 成功运行
- ✅ 输出：`picorv32_netlist.v` (839KB), `picorv32_netlist.json` (2.9MB)
- ✅ 含 `memory_map` 展开（将寄存器文件展开为独立触发器）
- ✅ 含 `fix_netlist.py` 后处理（展开复杂拼接赋值）

### 3.2 iEDA 后端流程（✅ 已验证，部分步骤有已知问题）
- ✅ Floorplan (iFP)：成功生成 500um x 500um 布局，6211 instances, 20545 gates
- ✅ Placement (iPL)：成功完成全局布局和详细布局
- ✅ CTS (iCTS)：成功完成时钟树综合
- ⚠️ Routing (iRT)：有 DRC 迭代中的 pin access 问题（7.7GB 内存限制）
- ✅ STA (iSTA)：可在 CTS 结果上运行
- ⚠️ GDSII：依赖 Routing 完成

### 3.3 关键修复记录
| 问题 | 修复方案 |
|------|---------|
| `$::env(PDK_ROOT)` Yosys 不支持 | 改为模板替换 `__PDK_LIB_PATH__` |
| `write_sdc` 非 Yosys 命令 | 改为复制已有 SDC 文件 |
| iEDA Verilog parser 不支持 memory 数组 | 添加 `memory_map` pass |
| iEDA 不支持复杂拼接赋值 `{a[3], a[1]} = ...` | 创建 `fix_netlist.py` 展开为逐位赋值 |
| iEDA SDC 不支持 `remove_from_collection` | 简化 SDC 约束 |
| iEDA SDC 不支持 `set_clock_latency` | 进一步简化 SDC |
| HD/HS 单元库不匹配 | 创建自定义 `db_path_setting.tcl` 和配置文件 |
| 无 ROW 定义导致布局崩溃 | 修正 site 名称 `unit` → `unithd` |

---

## 四、KiCad 测试载板（✅ 已完成）

- ✅ PicoRV32 原理图符号（`kicad/symbols/picorv32.kicad_sym`）
- ✅ QFN-48 封装（`kicad/footprints/QFN-48_7x7mm_P0.5mm.kicad_mod`）
- ✅ 原理图设计（`kicad/test_board/test_board.kicad_sch`）
  - PicoRV32 实例
  - 去耦电容 (100nF)
  - 100MHz 晶振
  - 复位电路（上拉 + 按键）
  - JTAG 接口
  - GPIO 排针
- ✅ 四层 PCB Layout（`kicad/test_board/test_board.kicad_pcb`）
  - 尺寸：40mm x 30mm
  - 层叠：F.Cu / In1.Cu (GND) / In2.Cu (PWR) / B.Cu
  - 安装孔、接插件、晶振布局

---

## 五、文档与博客（✅ 已完成）

### 5.1 教程
| 文件 | 内容 |
|------|------|
| `docs/tutorials/01_setup_guide.md` | 环境搭建指南 |
| `docs/tutorials/02_synthesis_guide.md` | Yosys 综合教程 |
| `docs/tutorials/03_backend_flow.md` | iEDA 后端流程教程 |
| `docs/tutorials/04_kicad_testboard.md` | KiCad 测试载板设计教程 |

### 5.2 博客
| 文件 | 内容 |
|------|------|
| `docs/blog/2026_04_30_project_launch.md` | 项目启动博客 |
| `docs/blog/2026_04_30_ieda_integration.md` | iEDA 集成经验分享 |

---

## 六、测试（✅ 已完成）

### 6.1 仿真测试
- ✅ `tests/simulation/tb_picorv32.v` - 测试平台
- ✅ `tests/simulation/test.hex` - 测试程序
- ✅ `tests/simulation/Makefile` - 仿真构建脚本

### 6.2 形式验证
- ✅ `tests/formal/picorv32.sby` - SymbiYosys 配置
- ✅ `tests/formal/properties.v` - 形式验证属性
- ✅ `tests/formal/run_formal.sh` - 运行脚本
- ✅ `tests/formal/README.md` - 说明文档

---

## 七、GitHub 仓库（✅ 已完成）

- ✅ `git init` 初始化
- ✅ 首次 commit（58 文件，~11500 行）
- ⏳ 推送到远程仓库（需要 GitHub 认证）

---

## 八、已知限制和后续工作

1. **iEDA Routing 收敛**：在 7.7GB 内存环境下，布线步骤的 pin access 迭代可能无法完全收敛。需要更大内存或优化布局密度。
2. **SDC 约束简化**：iEDA STA 引擎仅支持基本 SDC 命令（`create_clock`, `set_clock_uncertainty`），不支持 `set_input_delay` 等高级约束。
3. **单元库选择**：当前使用 HD（高密度）库。HS（高速）库可能在时序上更优，但需要更新所有配置。
4. **iEDA 构建**：源码需要重新编译（CMake + make），预计 30-60 分钟。
