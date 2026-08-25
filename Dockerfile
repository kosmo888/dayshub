# ========== 阶段1: 构建依赖 ==========
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ========== 阶段2: 运行时 ==========
FROM python:3.12-slim

LABEL maintainer="DaysHub"
LABEL description="DaysHub v1.1.0 - 时光看板与纪念日中心"
LABEL version="1.1.0"

WORKDIR /app

# 拷贝已安装的依赖
COPY --from=builder /install /usr/local

# 安装 tzdata 并设置时区
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# 拷贝源码（.dockerignore 已排除 data/ __pycache__/ .git/ 等）
COPY . .

# 数据目录
RUN mkdir -p /app/data
VOLUME /app/data

# 环境变量
ENV DAYSHUB_PORT=5217
ENV DAYSHUB_DATA_DIR=/app/data
ENV DAYSHUB_TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

EXPOSE 5217

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5217/health', timeout=3)" || exit 1

CMD ["python3", "app.py"]