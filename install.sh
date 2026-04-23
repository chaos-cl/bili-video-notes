#!/bin/bash
# Bilibili Notes 安装脚本
# 用法: bash install.sh [--skip-bili] [--skip-ffmpeg] [--skip-ytdlp]
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKIP_BILI=false
SKIP_FFMPEG=false
SKIP_YTDLP=false

for arg in "$@"; do
  case "$arg" in
    --skip-bili)    SKIP_BILI=true ;;
    --skip-ffmpeg)  SKIP_FFMPEG=true ;;
    --skip-ytdlp)   SKIP_YTDLP=true ;;
  esac
done

echo "========================================="
echo " Bilibili Notes 安装脚本"
echo "========================================="
echo ""

# ---------- 1. 检查 Python ----------
echo ">>> 检查 Python 环境"
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 12 ]; then
        info "Python $PY_VERSION"
    else
        fail "需要 Python >= 3.12，当前 $PY_VERSION。请升级: brew install python@3.12"
    fi
else
    fail "未找到 python3。请安装: brew install python@3.12"
fi

# ---------- 2. 检查/安装 uv ----------
echo ""
echo ">>> 检查 uv 包管理器"
if command -v uv &>/dev/null; then
    info "uv $(uv --version)"
else
    warn "uv 未安装，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv &>/dev/null; then
        info "uv $(uv --version)"
    else
        fail "uv 安装失败，请手动安装: https://docs.astral.sh/uv/"
    fi
fi

# ---------- 3. 安装 Python 依赖 ----------
echo ""
echo ">>> 安装 Python 依赖"
cd "$SCRIPT_DIR"
uv sync
info "Python 依赖安装完成"

# ---------- 4. 检查/安装 bilibili-cli ----------
echo ""
echo ">>> 检查 bilibili-cli"
if [ "$SKIP_BILI" = true ]; then
    warn "跳过 bilibili-cli 检查"
elif command -v bili &>/dev/null; then
    info "bili $(bili --version 2>/dev/null || echo '已安装')"
    # 检查是否已登录
    if bili status &>/dev/null 2>&1; then
        info "bili 已认证"
    else
        warn "bili 未登录，请运行: bili auth login"
    fi
else
    warn "bili 未安装"
    echo ""
    echo "  安装方式（任选其一）："
    echo "  1. brew install bilibili-cli"
    echo "  2. 从源码安装: https://github.com/public-clis/bilibili-cli"
    echo ""
    read -p "  是否尝试 brew 安装? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install bilibili-cli 2>/dev/null || warn "brew 安装失败，请手动安装"
        if command -v bili &>/dev/null; then
            info "bili 安装成功，请运行: bili auth login"
        fi
    fi
fi

# ---------- 5. 检查/安装 ffmpeg ----------
echo ""
echo ">>> 检查 ffmpeg"
if [ "$SKIP_FFMPEG" = true ]; then
    warn "跳过 ffmpeg 检查"
elif command -v ffmpeg &>/dev/null; then
    info "ffmpeg $(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}')"
else
    warn "ffmpeg 未安装，正在安装..."
    brew install ffmpeg
    if command -v ffmpeg &>/dev/null; then
        info "ffmpeg 安装成功"
    else
        fail "ffmpeg 安装失败，请手动安装: brew install ffmpeg"
    fi
fi

# ---------- 6. 检查/安装 yt-dlp ----------
echo ""
echo ">>> 检查 yt-dlp"
if [ "$SKIP_YTDLP" = true ]; then
    warn "跳过 yt-dlp 检查"
elif command -v yt-dlp &>/dev/null; then
    info "yt-dlp $(yt-dlp --version)"
else
    warn "yt-dlp 未安装，正在安装..."
    brew install yt-dlp
    if command -v yt-dlp &>/dev/null; then
        info "yt-dlp 安装成功"
    else
        fail "yt-dlp 安装失败，请手动安装: brew install yt-dlp"
    fi
fi

# ---------- 7. 配置 MINIMAX_API_KEY ----------
echo ""
echo ">>> 检查 MiniMax API 密钥"
if [ -n "$MINIMAX_API_KEY" ]; then
    info "MINIMAX_API_KEY 已设置"
else
    warn "MINIMAX_API_KEY 未设置"
    echo ""
    echo "  请获取 API 密钥后设置环境变量："
    echo "  export MINIMAX_API_KEY=\"your-key-here\""
    echo ""
    echo "  添加到 shell 配置以持久化："
    echo "  echo 'export MINIMAX_API_KEY=\"your-key-here\"' >> ~/.zshrc"
fi

# ---------- 8. 检查 config.yaml ----------
echo ""
echo ">>> 检查配置文件"
if [ -f "$SCRIPT_DIR/config.yaml" ]; then
    info "config.yaml 存在"
else
    warn "config.yaml 不存在"
    echo ""
    read -p "  请输入 Obsidian vault 路径 [~/Documents/Bilibili/Bilibili]: " VAULT_PATH
    VAULT_PATH="${VAULT_PATH:-~/Documents/Bilibili/Bilibili}"
    # 更新 config.yaml 中的 vault_path
    if command -v sed &>/dev/null; then
        sed -i.bak "s|~/Documents/Bilibili/Bilibili|$VAULT_PATH|g" "$SCRIPT_DIR/config.yaml" 2>/dev/null || true
    fi
    info "vault_path 已设置为: $VAULT_PATH"
fi

# ---------- 9. 创建输出目录 ----------
echo ""
echo ">>> 创建输出目录"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/work"
info "临时目录创建完成"

# ---------- 完成 ----------
echo ""
echo "========================================="
info "安装完成！"
echo "========================================="
echo ""
echo "使用方法："
echo "  # 单个视频"
echo "  uv run python scripts/pipeline.py --bv BV1ABcsztEcY"
echo ""
echo "  # 视频URL"
echo "  uv run python scripts/pipeline.py --url \"https://www.bilibili.com/video/BV1ABcsztEcY\""
echo ""
echo "  # 批量处理UP主"
echo "  uv run python scripts/pipeline.py --user \"影视飓风\" --max 10"
echo ""
echo "  # 如需使用本地 oMLX 推理，编辑 config.yaml 启用 omlx 配置"
echo ""

# 环境摘要
echo "--- 环境摘要 ---"
echo "Python:  $(python3 --version 2>/dev/null || echo 'N/A')"
echo "uv:      $(uv --version 2>/dev/null || echo 'N/A')"
echo "bili:    $(command -v bili &>/dev/null && echo '已安装' || echo '未安装')"
echo "ffmpeg:  $(command -v ffmpeg &>/dev/null && echo '已安装' || echo '未安装')"
echo "yt-dlp:  $(command -v yt-dlp &>/dev/null && echo '已安装' || echo '未安装')"
echo "MiniMax: $([ -n \"$MINIMAX_API_KEY\" ] && echo '已配置' || echo '未配置')"
