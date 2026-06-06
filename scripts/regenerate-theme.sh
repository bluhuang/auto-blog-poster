#!/usr/bin/env bash
# 重新生成主题 CSS
#
# 主题的 themeGenerator.js 优先读 themes/hugoplate/exampleSite/data/theme.json
# （"theme setup mode"），但本项目的唯一配置源是根目录的 data/theme.json。
# 这个 wrapper 负责把根配置同步到 exampleSite，再跑原脚本。
#
# 使用：bash scripts/regenerate-theme.sh
#       或  ./scripts/regenerate-theme.sh
#
# 不直接 commit themes/hugoplate/exampleSite/data/theme.json：
# 它会在每次构建时被根 data/theme.json 覆盖。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

ROOT_THEME_JSON="data/theme.json"
EXAMPLE_THEME_JSON="themes/hugoplate/exampleSite/data/theme.json"
EXAMPLE_HUGO_TOML="themes/hugoplate/exampleSite/hugo.toml"

if [ ! -f "$ROOT_THEME_JSON" ]; then
  echo "ERROR: $ROOT_THEME_JSON 不存在" >&2
  exit 1
fi

if [ ! -d "themes/hugoplate" ]; then
  echo "ERROR: themes/hugoplate submodule 未初始化" >&2
  exit 1
fi

# 同步根 theme.json → exampleSite/theme.json
mkdir -p "$(dirname "$EXAMPLE_THEME_JSON")"
cp "$ROOT_THEME_JSON" "$EXAMPLE_THEME_JSON"
echo "✓ 已同步 $ROOT_THEME_JSON → $EXAMPLE_THEME_JSON"

# 跑原脚本
node themes/hugoplate/scripts/themeGenerator.js

echo ""
echo "✓ 主题 CSS 已重新生成"
echo "  输出：themes/hugoplate/assets/css/generated-theme.css"
