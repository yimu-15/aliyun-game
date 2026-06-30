# =============================================================================
# 世界杯冠军预测 Agent — Dockerfile
# =============================================================================
# 多阶段构建: builder → runtime 缩小最终镜像体积
#
# 构建: docker build -t worldcup-predictor .
# 运行: docker run -p 8501:8501 worldcup-predictor
# =============================================================================

# ── Stage 1: Builder (安装依赖) ──
FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml .

# 安装构建依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        streamlit>=1.35.0 \
        pandas>=2.2.0 \
        numpy>=1.26.0 \
        scipy>=1.12.0 \
        plotly>=5.20.0 \
        pyyaml>=6.0 \
        fastapi>=0.110.0 \
        uvicorn[standard]>=0.29.0

# ── Stage 2: Runtime (精简) ──
FROM python:3.11-slim AS runtime

WORKDIR /app

# 从 builder 复制已安装的 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目代码 (只复制需要的目录)
COPY config/ ./config/
COPY models/ ./models/
COPY utils/  ./utils/
COPY app/    ./app/
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY main.py ./main.py

# 创建数据目录
RUN mkdir -p /app/data/raw /app/data/processed /app/data/logs

# 暴露端口
EXPOSE 8501 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8501/_stcore/health', timeout=5)" || exit 1

# 默认启动 Streamlit
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
