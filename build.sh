#!/bin/bash
set -e

echo "========================================"
echo "  AI 同声传译助手 - 一键打包脚本"
echo "========================================"
echo ""

# ── 检查 Python ──
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请安装 Python 3.11+"
    exit 1
fi

# ── 检查 Node.js ──
if ! command -v node &> /dev/null; then
    echo "[错误] 未找到 Node.js，请安装 Node.js 18+"
    exit 1
fi

# ── Step 1: 打包 Python 后端 ──
echo ""
echo "[1/3] 打包 Python 后端..."
echo ""

cd backend

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "[警告] 未找到虚拟环境，使用全局 Python"
fi

# 安装 PyInstaller
pip install pyinstaller --quiet

# 清理旧的构建产物
rm -rf dist build

# 打包
pyinstaller ai-translate-backend.spec --noconfirm

echo "[完成] 后端打包成功"
cd ..

# ── Step 2: 构建前端 ──
echo ""
echo "[2/3] 构建前端..."
echo ""

cd frontend

# 安装依赖
npm install

# 构建 Electron 应用
npm run electron:build

echo "[完成] 前端构建成功"
cd ..

# ── Step 3: 完成 ──
echo ""
echo "========================================"
echo "  打包完成！"
echo "========================================"
echo ""
echo "安装包位置: frontend/release/"
echo ""
ls -la frontend/release/*.dmg 2>/dev/null || true
ls -la frontend/release/*.zip 2>/dev/null || true
echo ""
