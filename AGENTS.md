# OpenCode 项目指南

## 关键上下文（必须遵守）

### 本地 Obsidian 仓库
- 本地 Vault 路径：`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/blu obsidian`
- **不要**因为 GitHub 上的仓库是私有就说无法访问。你**有本地直接访问权限**。读取笔记内容、检查文件时间、测试图片提取时都用这个本地路径。
- 只有在 GitHub Actions（CI）中才需要用 `GH_PAT` 从 GitHub 克隆仓库。

### 配置优先级
- **`config.yaml` 是唯一配置来源**（路径、API 密钥、处理开关、图片查找规则等）。
- **禁止硬编码**任何路径、目录名或参数。必须从 `config.yaml` 读取。
- 如果配置项缺失，给出合理默认值，但需要警告用户。

### 图片处理（关键）
- 图片查找逻辑必须遵循 Obsidian 的 `attachmentFolderPath` 设置（从源仓库的 `.obsidian/app.json` 中读取）。
- 修改任何图片相关代码后，**必须进行端到端验证**：
  1. 运行 `python main.py`（或至少处理一篇包含 `![[example.png]]` 的笔记）。
  2. 检查图片文件是否被复制到 `static/images/` 下（实际文件存在性）。
  3. 检查生成的 `content/.../note.md` 中图片链接是否已被替换为 `/images/...`。
  4. 启动 `hugo server`，在浏览器中打开对应文章，确认图片被渲染（不仅仅是 HTTP 200）。
- **不要**只检查图片 URL 返回 200，那只能说明文件存在，不能证明链接转换正确或 HTML 渲染成功。

### 常见错误禁止清单
- **不要**因为 GitHub 私有仓库无法访问就放弃。你有本地 Vault，直接使用。
- **不要**在恢复缓存时删除 `content/about.md` 等手动创建的页面。使用合并策略（保留本地独有文件）。
- **不要**将 `content/`、`static/images/`、`.hash_cache.json`、`.deepseek_cache.json`、`.file_times.json` 提交到 `auto-blog-poster` 仓库。它们只应持久化到 `blogs-of-bluhuang` 的 `processed-cache` 分支。
- **不要**擅自修改 `force_reprocess_all` 标志。在强制全量处理后，自动将其重置为 `false`。

## 测试与验证要求

在标记任务完成并提交之前，**必须**：
1. **快速测试**一小部分数据（例如一篇笔记），确保没有语法错误或崩溃。
2. **如果修改了图片处理**，执行上述端到端验证。
3. **如果修改了 Hugo 模板**，运行 `hugo server` 并手动检查页面布局（至少确保站点能构建成功）。
4. **检查笔记数量**：运行 `main.py` 后，确认处理的笔记数量与源笔记数量基本一致（或至少没有重要笔记被遗漏）。

## 代码风格与约定
- 函数和变量使用 `snake_case`。
- 进度日志使用 `print`（例如 `[1/4] Pulling source...`）。错误信息使用 `sys.stderr.write`。
- 调用外部 API（DeepSeek）时实现重试机制（最多3次，指数退避）。
- 文件操作优先使用 `pathlib.Path`，保证跨平台兼容。

## Git 版本兼容性（重要！）
- 系统 `/usr/bin/git` 版本 2.22.0（过于老旧，不支持 `--end-of-options`）
- Hugo 模块系统需要 `git ls-remote --end-of-options`（git ≥ 2.42）
- **每次构建前**必须设置：`PATH="/tmp:/usr/local/bin:/usr/bin:/bin" hugo ...`
  - `/tmp/git` 是一个指向 brew git 的包装脚本
  - brew git 位于 `/usr/local/opt/git/bin/git`（2.54.0）
  - 如果 `/tmp/git` 不存在，运行：
    ```
    cat > /tmp/git << 'GITEOF'
    #!/bin/bash
    /usr/local/opt/git/bin/git "$@"
    GITEOF
    chmod +x /tmp/git
    ```
- 在 GitHub Actions（CI）中没有此问题，因为 CI 的 git 版本足够新

## 关于页面（About）渲染
- `content/about.md` **不能**有 `layout: about` 前注，否则 Hugo 会使用主题的 `themes/hugoplate/layouts/about.html`（单栏居中布局，不含 personal-intro）
- 改用 `layouts/_default/single.html` 中的条件判断：`{{ if eq .Title "About" }}{{ partial "personal-intro" . }}{{ end }}`
- 这确保了 about 页自动使用两栏布局（tree-nav + content）并正确渲染 personal-intro

## 项目结构提醒
- `modules/`：核心逻辑（git_ops, content_processor, obsidian_parser, deepseek_client, hugo_builder, deployer, cache_persister）
- `content/`：处理后的 Markdown（不提交）
- `static/images/`：复制的图片（不提交）
- `.temp/`：临时克隆的源仓库和部署仓库（忽略）
- `.github/workflows/deploy.yml`：CI 流水线

## 沟通方式
- 在做出重大变更（如重新设计布局、新增模块）前，**先解释计划**，等待用户确认。
- 遇到模棱两可的情况（如配置缺失、文件结构异常），**先询问用户**，不要猜测。
- 全程使用中文回答。

## 记住
- 用户重视**自动化**和**可靠性**。不要留下半途而废的问题。
- 如果问题反复出现（如图片不显示），深入排查：检查日志、中间文件、最终的 HTML 渲染。
- 不确定时，参考历史对话和现有代码模式。
