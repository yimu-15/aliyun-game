#!/bin/bash
# =============================================================================
# Docker 容器启动脚本 — 同时启动 FastAPI 后端 + Streamlit 前端
# =============================================================================
set -e

echo "=========================================="
echo " 世界杯冠军预测 Agent — Docker 启动"
echo "=========================================="

# 启动 FastAPI 后端 (后台)
echo "[1/2] 启动 FastAPI 后端 (port 8000)..."
python backend/main.py &
BACKEND_PID=$!
sleep 2

# 启动 Streamlit 前端 (前台)
echo "[2/2] 启动 Streamlit 前端 (port 8501)..."
exec streamlit run app/main.py --server.port=8501 --server.address=0.0.0.0
