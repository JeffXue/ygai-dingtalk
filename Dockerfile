# 使用官方 Python 3.12 轻量级镜像作为基础镜像
FROM python:3.12-slim

# 设置环境变量，防止 Python 生成 .pyc 文件，并强制将标准输出和标准错误直接打印（不放入缓冲）
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 设置工作目录
WORKDIR /app

# 安装系统级依赖（比如编译一些 Python 包可能需要的 gcc 等），然后清理缓存减小镜像体积
RUN apt-get update && apt-get install -y \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 将 requirements.txt 复制到容器中
COPY requirements.txt /app/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将项目的所有代码复制到容器中
COPY . /app/
