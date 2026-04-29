# KiCad 测试板设计教程

> 本教程介绍如何使用 KiCad 设计 SiliconTrace Open 项目的测试 PCB 板。涵盖原理图符号创建、封装设计、原理图绘制、4 层 PCB 布局以及电源完整性基础知识。

## 目录

- [1. 概述](#1-概述)
- [2. 创建 IC 芯片原理图符号](#2-创建-ic-芯片原理图符号)
- [3. 设计 QFN/BGA 封装](#3-设计-qfnbga-封装)
- [4. 原理图设计](#4-原理图设计)
- [5. 四层 PCB 布局指南](#5-四层-pcb-布局指南)
- [6. 电源完整性基础](#6-电源完整性基础)
- [7. 信号完整性基础](#7-信号完整性基础)
- [8. 生成制造文件](#8-生成制造文件)

---

## 1. 概述

### 1.1 测试板的目的

测试板（Test Board）用于验证 SiliconTrace Open 设计的 PicoRV32 芯片功能，主要包括：

- 芯片供电和电源管理
- 时钟信号提供
- 复位电路
- JTAG 调试接口
- GPIO 引出
- 测试点（Test Points）

### 1.2 测试板架构

```
                    ┌─────────────────────────────────────────┐
                    │              Test Board                  │
                    │                                         │
   USB ──────────►  │  ┌─────────┐    ┌──────────────────┐   │
                    │  │  USB    │    │  PicoRV32 Chip   │   │
   Power ────────►  │  │  to     │───►│  (QFN48/BGA64)   │   │
                    │  │  UART   │    │                  │   │
   JTAG ─────────►  │  └─────────┘    └──────────────────┘   │
                    │      │                    │              │
                    │  ┌───┴───┐          ┌─────┴─────┐      │
                    │  │ FTDI  │          │  Test      │      │
                    │  │ FT2232│          │  Points    │      │
                    │  └───────┘          └───────────┘      │
                    │                                         │
                    │  ┌───────────┐  ┌───────────┐          │
                    │  │ 3.3V Reg  │  │ 1.8V Reg  │          │
                    │  └───────────┘  └───────────┘          │
                    │                                         │
                    └─────────────────────────────────────────┘
```

### 1.3 芯片封装选择

对于 SiliconTrace 项目，推荐使用 QFN-48 封装：

| 参数 | 值 |
|------|-----|
| 封装类型 | QFN-48 |
| 尺寸 | 7mm x 7mm |
| 引脚间距 | 0.5mm |
| 焊盘尺寸 | 0.3mm x 0.8mm |
| 热焊盘 | 5.5mm x 5.5mm |

---

## 2. 创建 IC 芯片原理图符号

### 2.1 打开符号编辑器

1. 启动 KiCad
2. 点击 "Symbol Editor"
3. 创建新库: File -> New Library -> 选择 "Project" 或 "Global"

### 2.2 创建 PicoRV32 符号

```
# PicoRV32 引脚分配 (QFN-48)

# 电源引脚
VDD_1    Pin 1   - VDD (3.3V)
VDD_2    Pin 13  - VDD (3.3V)
VDD_3    Pin 25  - VDD (3.3V)
VDD_4    Pin 37  - VDD (3.3V)
VSS_1    Pin 2   - VSS (GND)
VSS_2    Pin 14  - VSS (GND)
VSS_3    Pin 26  - VSS (GND)
VSS_4    Pin 38  - VSS (GND)

# 核心信号
CLK      Pin 3   - 时钟输入
RESETN   Pin 4   - 复位（低有效）

# 内存接口
MEM_VALID  Pin 5  - 内存有效
MEM_ADDR0  Pin 6  - 地址位 0
MEM_ADDR1  Pin 7  - 地址位 1
...
MEM_ADDR31 Pin 37 - 地址位 31
MEM_WDATA0 Pin 38 - 写数据位 0
...
MEM_WDATA31 Pin 69 - 写数据位 31
MEM_WSTRB0  Pin 70 - 写选通位 0
...
MEM_WSTRB3  Pin 73 - 写选通位 3
MEM_READY   Pin 74 - 内存就绪
MEM_RDATA0  Pin 75 - 读数据位 0
...
MEM_RDATA31 Pin 106 - 读数据位 31

# 中断
IRQ0     Pin 107 - 中断 0
...
IRQ31    Pin 138 - 中断 31

# JTAG (可选)
JTAG_TMS  Pin 139
JTAG_TCK  Pin 140
JTAG_TDI  Pin 141
JTAG_TDO  Pin 142

# GPIO
GPIO0     Pin 143
...
GPIO15    Pin 158
```

### 2.3 符号绘制步骤

1. **绘制矩形框**: 代表芯片主体
2. **添加引脚**: 为每个引脚添加名称和编号
3. **设置引脚类型**: Input, Output, Bidirectional, Power, Passive
4. **添加属性**: 值、参考标识、封装关联

### 2.4 符号属性设置

| 属性 | 值 |
|------|-----|
| Reference | U |
| Value | PicoRV32 |
| Footprint | Package_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.5x5.5mm |
| Datasheet | https://github.com/YosysHQ/picorv32 |
| Description | PicoRV32 RISC-V Core |

### 2.5 引脚分组

为了原理图可读性，将引脚分组：

```
Group: Power
  VDD (Power Input)
  VSS (Power Input)

Group: Clock & Reset
  CLK (Input)
  RESETN (Input)

Group: Memory Bus
  MEM_VALID (Output)
  MEM_ADDR[31:0] (Output)
  MEM_WDATA[31:0] (Output)
  MEM_WSTRB[3:0] (Output)
  MEM_READY (Input)
  MEM_RDATA[31:0] (Input)

Group: Interrupts
  IRQ[31:0] (Input)

Group: JTAG
  JTAG_TMS (Input)
  JTAG_TCK (Input)
  JTAG_TDI (Input)
  JTAG_TDO (Output)

Group: GPIO
  GPIO[15:0] (Bidirectional)
```

---

## 3. 设计 QFN/BGA 封装

### 3.1 打开封装编辑器

1. 启动 KiCad
2. 点击 "Footprint Editor"
3. 创建新库或打开现有库

### 3.2 QFN-48 封装参数

```yaml
# QFN-48 封装规格
package:
  name: QFN-48
  body_size: 7.0mm x 7.0mm
  height: 0.75mm
  lead_pitch: 0.5mm
  lead_count: 48

pad:
  size: 0.3mm x 0.8mm
  shape: rectangle
  pitch: 0.5mm
  distance_to_ep: 0.2mm

thermal_pad:
  size: 5.5mm x 5.5mm
  openings:
    - size: 0.4mm x 0.4mm
    - pitch: 1.2mm
    - pattern: grid

solder_mask:
  expansion: 0.05mm

paste:
  reduction: 0.1mm
```

### 3.3 绘制封装步骤

1. **设置网格**: 0.05mm 或 0.025mm
2. **放置焊盘**:
   - 按 QFN 规格放置 48 个外围焊盘
   - 放置中心热焊盘（Thermal Pad）
   - 设置焊盘尺寸和形状
3. **绘制丝印层**:
   - 芯片轮廓（Fab 层）
   - 引脚 1 标记
   - 参考标识
4. **绘制阻焊层**:
   - 焊盘区域阻焊开窗
5. **设置 courtyard**:
   - 封装占用区域

### 3.4 热焊盘设计

热焊盘（Thermal Pad）设计注意事项：

```
        ┌─────────────────────────────┐
        │                             │
        │   ○   ○   ○   ○   ○   ○    │  ← 热焊盘过孔阵列
        │                             │
        │   ○   ○   ○   ○   ○   ○    │
        │                             │
        │   ○   ○   ○   ○   ○   ○    │
        │                             │
        └─────────────────────────────┘

○ = 过孔 (0.3mm 直径, 0.6mm 间距)
```

- 过孔直径: 0.3mm
- 过孔间距: 0.6mm (2 倍直径)
- 过孔连接: GND (VSS)
- 阻焊开窗: 热焊盘区域

### 3.5 BGA 封装设计（可选）

如果选择 BGA 封装：

```yaml
# BGA-64 封装规格
package:
  name: BGA-64
  body_size: 8.0mm x 8.0mm
  ball_pitch: 0.8mm
  ball_count: 64

ball:
  diameter: 0.4mm
  pad_diameter: 0.35mm
  solder_mask_diameter: 0.45mm

rows: 8x8
row_names: [A, B, C, D, E, F, G, H]
column_names: [1, 2, 3, 4, 5, 6, 7, 8]
```

---

## 4. 原理图设计

### 4.1 原理图结构

测试板原理图分为以下几个部分：

1. **电源部分**: LDO 稳压器、滤波电容
2. **核心芯片**: PicoRV32
3. **时钟电路**: 晶振或时钟发生器
4. **复位电路**: RC 复位电路
5. **调试接口**: JTAG/SWD
6. **串口通信**: USB-UART
7. **GPIO 扩展**: LED、按钮、连接器

### 4.2 电源电路设计

#### 3.3V 电源

```
     ┌─────────┐
     │ AMS1117 │
     │  -3.3   │
VIN ─┤IN   OUT├───┬─── 3.3V
     │   ADJ   │   │
     └────┬────┘  ┌┴┐
          │       │ │ C1 (10uF)
         ┌┴┐      │ │
         │ │ R1   └┬┘
         │ │      ─┴─ GND
         └┬┘
          │
         ─┴─ GND
```

#### 1.8V 电源

```
     ┌─────────┐
     │ AMS1117 │
     │  -1.8   │
3.3V─┤IN   OUT├───┬─── 1.8V (Core)
     │   ADJ   │   │
     └────┬────┘  ┌┴┐
          │       │ │ C2 (10uF)
         ┌┴┐      │ │
         │ │ R2   └┬┘
         │ │      ─┴─ GND
         └┬┘
          │
         ─┴─ GND
```

### 4.3 时钟电路

```
           ┌─────────┐
    ┌──────┤ Osc Out  │
    │      │  50MHz   │
    │      │          │
    │      └──────────┘
    │
    │    ┌───────┐
    ├───►│ CLK   │
    │    │Buffer │
    │    └───────┘
    │         │
    │         ▼
    │    ┌─────────┐
    └───►│ PicoRV32│
         │   CLK   │
         └─────────┘
```

### 4.4 复位电路

```
     3.3V
      │
     ┌┴┐
     │ │ R (10K)
     │ │
     └┬┘
      ├─────────────────► RESETN (PicoRV32)
      │
     ─┴─ C (100nF)
      │
     ─┴─ GND

     ┌──────┐
     │      │
SW ──┘      ├──────────► RESETN
     │      │
    ─┴─    ─┴─
     │      │
    GND    GND
```

### 4.5 JTAG 接口

```
JTAG Header (20-pin ARM)
┌──────────────────────┐
│  1  3  5  7  9  11  │
│  2  4  6  8  10 12  │
└──────────────────────┘

Pin 1: VCC (3.3V)
Pin 3: nTRST
Pin 5: TDI
Pin 7: TMS
Pin 9: TCK
Pin 11: RTCK
Pin 13: TDO
Pin 15: nRESET
Pin 17-20: GND
```

### 4.6 USB-UART 电路

```
USB Type-B
┌──────────┐
│ D-  (2)  │──────► FTDI FT2232H
│ D+  (3)  │──────► FTDI FT2232H
│ VCC (1)  │──────► 5V
│ GND (4)  │──────► GND
└──────────┘

FTDI FT2232H
┌──────────┐
│ TXD ─────│──────► PicoRV32 RX
│ RXD ─────│◄────── PicoRV32 TX
│ RTS ─────│──────► PicoRV32 CTS
│ CTS ─────│◄────── PicoRV32 RTS
└──────────┘
```

### 4.7 原理图绘制步骤

1. **创建新项目**: File -> New Project
2. **放置符号**: 从库中选择组件
3. **连线**: 使用 Wire 工具连接引脚
4. **添加网络标签**: 为重要信号添加标签
5. **添加电源符号**: VCC, GND
6. **添加注释**: 文本框、表格
7. **运行 ERC**: 电气规则检查
8. **生成网表**: 用于 PCB 布局

---

## 5. 四层 PCB 布局指南

### 5.1 层叠设计

四层板推荐层叠：

```
Layer 1 (Top):     Signal + Components
Layer 2 (Inner 1): GND Plane (完整地平面)
Layer 3 (Inner 2): Power Plane (电源层)
Layer 4 (Bottom):  Signal + Components
```

| 层 | 名称 | 厚度 | 用途 |
|----|------|------|------|
| Top | Signal | 35um | 信号线、元件 |
| Inner 1 | GND | 35um | 地平面 |
| Inner 2 | PWR | 35um | 电源平面 |
| Bottom | Signal | 35um | 信号线、元件 |

### 5.2 PCB 尺寸设计

```
推荐 PCB 尺寸: 100mm x 80mm

安装孔: 4 个 M3 螺丝孔
位置: 四角，距边缘 5mm

    ┌────────────────────────────────────────┐
    │  ○                                  ○  │
    │                                        │
    │                                        │
    │        ┌────────────────────┐          │
    │        │    PicoRV32        │          │
    │        │    (QFN-48)        │          │
    │        └────────────────────┘          │
    │                                        │
    │  ○                                  ○  │
    └────────────────────────────────────────┘
```

### 5.3 元件布局原则

1. **就近原则**: 相关元件靠近放置
2. **信号流向**: 按信号流向布局
3. **电源规划**: 先布局电源部分
4. **去耦电容**: 紧贴芯片电源引脚
5. **晶振布局**: 靠近时钟输入引脚

### 5.4 去耦电容布局

```
     ┌────────────────────────┐
     │     PicoRV32 Chip      │
     │                        │
     │  VDD    VDD    VDD     │
     │   │      │      │     │
     └───┼──────┼──────┼─────┘
         │      │      │
        ┌┴┐    ┌┴┐    ┌┴┐
        │C│    │C│    │C│ 100nF (0402)
        └┬┘    └┬┘    └┬┘
         │      │      │
        GND    GND    GND

去耦电容布局原则:
- 每个 VDD 引脚配一个 100nF 电容
- 电容尽量靠近引脚
- 过孔直接连接到 GND 平面
```

### 5.5 布线规则

#### 信号线规则

| 信号类型 | 最小线宽 | 推荐线宽 | 说明 |
|---------|---------|---------|------|
| 普通信号 | 0.15mm | 0.2mm | 一般信号 |
| 时钟信号 | 0.2mm | 0.3mm | 时钟线 |
| 电源线 | 0.3mm | 0.5mm | 大电流 |
| JTAG | 0.2mm | 0.25mm | 调试接口 |

#### 差分线规则

```
差分线 (如 USB):
- 线宽: 0.2mm
- 线间距: 0.2mm
- 差分阻抗: 90 ohm
- 长度匹配: ±5mm
```

### 5.6 电源层分割

```
Inner Layer 2 (Power Plane):
┌────────────────────────────────────┐
│                                    │
│    ┌──────────────────────┐       │
│    │      3.3V 区域       │       │
│    │                      │       │
│    └──────────────────────┘       │
│                                    │
│    ┌──────────────────────┐       │
│    │      1.8V 区域       │       │
│    │                      │       │
│    └──────────────────────┘       │
│                                    │
│           GND 区域                 │
│                                    │
└────────────────────────────────────┘
```

### 5.7 PCB 设计检查清单

- [ ] 所有元件已放置
- [ ] 电源完整性检查
- [ ] 信号完整性检查
- [ ] DRC 检查通过
- [ ] ERC 检查通过
- [ ] 丝印清晰可读
- [ ] 安装孔位置正确
- [ ] 板边距足够
- [ ] 阻焊层正确
- [ ] 助焊层正确

---

## 6. 电源完整性基础

### 6.1 电源完整性概念

电源完整性（Power Integrity, PI）确保芯片获得稳定、干净的电源。

### 6.2 PDN 设计

电源分配网络（PDN）设计：

```
VRM ──── Bulk Cap ──── PCB Plane ──── Decoupling Cap ──── Package ──── Die
  │         │              │               │               │           │
  └───┬─────┘──────────────┘───────────────┘───────────────┘───────────┘
      │
      └── 低频响应 (> 100KHz)
```

### 6.3 去耦电容选择

| 电容值 | 封装 | 频率范围 | 用途 |
|--------|------|---------|------|
| 10uF | 0805 | 低频 | 体电容 |
| 1uF | 0603 | 中频 | 板级去耦 |
| 100nF | 0402 | 高频 | 芯片去耦 |
| 10nF | 0201 | 超高频 | 片上去耦 |

### 6.4 电源平面设计

```
推荐电源平面设计:
- 使用完整的电源层
- 避免电源层分割过多
- 电源层与地层紧密耦合
- 去耦电容过孔直接连接
```

---

## 7. 信号完整性基础

### 7.1 信号完整性概念

信号完整性（Signal Integrity, SI）确保信号在传输过程中保持质量。

### 7.2 关键参数

| 参数 | 说明 | 典型值 |
|------|------|--------|
| 阻抗 | 传输线特性阻抗 | 50 ohm (单端) |
| 反射 | 阻抗不匹配导致 | < 10% |
| 串扰 | 相邻信号线干扰 | < 5% |
| 时延 | 信号传播延迟 | 设计相关 |

### 7.3 传输线设计

```
微带线 (Microstrip):
┌─────────────────────┐
│     Signal          │ ← Signal Layer
├─────────────────────┤
│     Dielectric      │ ← FR4 (Er = 4.2)
├─────────────────────┤
│     GND Plane       │ ← Ground Layer
└─────────────────────┘

阻抗计算:
Z0 = (87 / sqrt(Er + 1.41)) * ln(5.98 * h / (0.8 * w + t))

其中:
Er = 介电常数 (FR4: 4.2)
h = 介质厚度
w = 线宽
t = 铜厚
```

### 7.4 串扰控制

```
减少串扰的方法:
- 增加线间距 (3W 规则)
- 使用地平面
- 缩短平行走线长度
- 使用差分信号
- 控制阻抗
```

---

## 8. 生成制造文件

### 8.1 Gerber 文件

```bash
# 在 KiCad 中生成 Gerber
File -> Plot -> 生成 Gerber

需要生成的层:
- F.Cu (Front Copper)
- In1.Cu (Inner 1 - GND)
- In2.Cu (Inner 2 - PWR)
- B.Cu (Back Copper)
- F.SilkS (Front Silkscreen)
- B.SilkS (Back Silkscreen)
- F.Mask (Front Solder Mask)
- B.Mask (Back Solder Mask)
- Edge.Cuts (Board Outline)
```

### 8.2 钻孔文件

```bash
# 生成钻孔文件
File -> Fabrication Outputs -> Drill Files

格式: Excellon
单位: mm
精度: 3:3
```

### 8.3 BOM 文件

```bash
# 生成 BOM
Tools -> Edit Symbol Fields -> Export BOM

BOM 包含:
- 参考标识
- 元件值
- 封装
- 数量
- 制造商
- 制造商编号
```

### 8.4 装配图

```bash
# 生成装配图
File -> Print -> 选择层

需要生成:
- 顶层装配图 (F.Fab + F.SilkS)
- 底层装配图 (B.Fab + B.SilkS)
```

### 8.5 制造文件检查清单

- [ ] Gerber 文件完整 (所有层)
- [ ] 钻孔文件正确
- [ ] BOM 文件完整
- [ ] 装配图清晰
- [ ] 文件命名规范
- [ ] 与制造商确认格式要求

---

## 总结

通过本教程，你已经学会了：

1. 创建 IC 芯片的原理图符号
2. 设计 QFN/BGA 封装
3. 绘制测试板原理图
4. 四层 PCB 布局设计
5. 电源完整性基础知识
6. 信号完整性基础知识
7. 生成制造文件

> **下一步**: 完成 PCB 设计后，可以将设计文件发送给 PCB 制造商进行打样。
