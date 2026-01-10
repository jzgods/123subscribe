# 第一阶段：构建阶段
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt文件并安装项目依赖到venv
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 第二阶段：运行阶段
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 创建日志目录
RUN mkdir -p /app/logs

# 从构建阶段复制venv和项目文件
COPY --from=builder /app/venv /app/venv
COPY . .

# 设置环境变量
ENV PATH="/app/venv/bin:$PATH"

# 暴露Flask应用使用的端口
EXPOSE 24512

# 可选：设置默认认证信息（建议在运行时通过-e参数覆盖）
# ENV APP_USERNAME=admin
# ENV APP_PASSWORD=password

# 设置容器启动命令
CMD ["python", "app.py"]