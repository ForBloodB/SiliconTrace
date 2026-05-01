# ============================================================
# 硅迹开源 - EDA 工具链 Docker 镜像
# 包含: Yosys, iEDA, KiCad, SKY130 PDK, SymbiYosys
# ============================================================
FROM ubuntu:22.04

LABEL maintainer="ForBloodB <3347432324@qq.com>"
LABEL description="SiliconTrace Open - Complete EDA toolchain for digital IC design"

# 避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# ============================================================
# 1. 系统依赖
# ============================================================
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    python3 \
    python3-pip \
    python3-venv \
    libboost-all-dev \
    libeigen3-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libtbb-dev \
    libgtest-dev \
    libgmp-dev \
    libffi-dev \
    libreadline-dev \
    zlib1g-dev \
    libbz2-dev \
    libsqlite3-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    tcl-dev \
    tk-dev \
    flex \
    bison \
    gawk \
    libreadline-dev \
    autoconf \
    automake \
    libtool \
    pkg-config \
    sudo \
    vim \
    nano \
    tree \
    htop \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# 2. 安装 Yosys
# ============================================================
RUN apt-get update && apt-get install -y yosys && rm -rf /var/lib/apt/lists/*

# ============================================================
# 3. 安装 KiCad
# ============================================================
RUN apt-get update && apt-get install -y kicad && rm -rf /var/lib/apt/lists/*

# ============================================================
# 4. 安装 Python 工具
# ============================================================
RUN pip3 install --no-cache-dir \
    volare \
    pyyaml \
    jinja2 \
    flask \
    flask-cors \
    openai \
    requests

# ============================================================
# 5. 设置环境变量（PDK 和 iEDA 通过 volume 挂载）
# ============================================================
ENV PDK_ROOT=/root/.volare
ENV IEDA_ROOT=/opt/iEDA
ENV IEDA_BIN=/opt/iEDA/scripts/design/sky130_gcd/iEDA
ENV PROJECT_ROOT=/workspace
ENV PATH="/opt/iEDA/scripts/design/sky130_gcd:${PATH}"

# ============================================================
# 7. 创建工作目录
# ============================================================
WORKDIR /workspace

# ============================================================
# 8. 复制项目文件
# ============================================================
COPY . /workspace/

# ============================================================
# 9. 设置入口点
# ============================================================
ENTRYPOINT ["/bin/bash"]
CMD ["-c", "echo '=== 硅迹开源 EDA 环境 ===' && echo 'Yosys:' && yosys -V && echo 'iEDA:' && ls -la /opt/iEDA/scripts/design/sky130_gcd/iEDA && echo 'KiCad:' && kicad --version 2>/dev/null || echo 'KiCad available' && echo 'SKY130 PDK:' && ls ~/.volare/sky130A/ 2>/dev/null | head -5 && echo '' && echo '使用方法: docker run -it silicontrace bash'"]
