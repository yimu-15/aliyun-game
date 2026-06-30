#!/bin/bash
# =============================================================================
# 世界杯冠军预测 Agent — 阿里云一键部署脚本
# =============================================================================
# 用法:
#   1. 在 ECS 上执行: bash scripts/deploy_aliyun.sh
#   2. 或本地构建推送: bash scripts/deploy_aliyun.sh build
# =============================================================================

set -e

PROJECT_DIR="/opt/worldcup-predictor"
COMPOSE_FILE="docker-compose.yml"

echo "=========================================="
echo " 世界杯冠军预测 Agent — 阿里云部署"
echo "=========================================="

# ── 检查 Docker ──
if ! command -v docker &> /dev/null; then
    echo "[1/5] 安装 Docker..."
    curl -fsSL https://get.docker.com | bash -s docker
    systemctl enable docker && systemctl start docker
else
    echo "[1/5] Docker 已安装"
fi

# ── 安装 docker-compose ──
if ! command -v docker-compose &> /dev/null; then
    echo "[2/5] 安装 docker-compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "[2/5] docker-compose 已安装"
fi

# ── 创建项目目录 ──
echo "[3/5] 创建项目目录..."
mkdir -p ${PROJECT_DIR}/data/{raw,processed,logs}
cd ${PROJECT_DIR}

# ── 拉取/更新镜像 ──
if [ "$1" == "build" ]; then
    echo "[4/5] 构建并推送镜像..."
    docker build -t worldcup-predictor:latest .
    # 推送到 ACR (取消注释并填入实际命名空间)
    # docker tag worldcup-predictor:latest registry.cn-hangzhou.aliyuncs.com/<ns>/worldcup-predictor:latest
    # docker push registry.cn-hangzhou.aliyuncs.com/<ns>/worldcup-predictor:latest
else
    echo "[4/5] 使用已有镜像..."
fi

# ── 启动服务 ──
echo "[5/5] 启动服务..."
docker-compose up -d

echo ""
echo "=========================================="
echo " 部署完成!"
echo "=========================================="
echo ""
echo " 访问地址:"
echo "   前端: http://$(curl -s ifconfig.me):8501"
echo "   API:  http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo " 管理命令:"
echo "   docker-compose ps              # 查看状态"
echo "   docker-compose logs -f         # 查看日志"
echo "   docker-compose restart         # 重启"
echo "   docker-compose down            # 停止"
echo ""
