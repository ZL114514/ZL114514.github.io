# ZL114514.github.io

个人博客，基于 MkDocs Material。

## 结构

```
mkdocs.yml      # 站点配置（主题、导航、插件）
src/            # Markdown 源文件 + 静态资源
  index.md
  about/
  blog/
    posts/      # 文章放这里
    .authors.yml
  stylesheets/
docs/           # 构建产物，GitHub Pages 直接从这里发布，不要手改
publish.sh      # 构建 + 提交 + 推送
```

## 写文章

在 `src/blog/posts/` 新建 `xxx.md`：

```yaml
---
date: 2026-10-06
categories:
  - 分类名
authors:
  - zl
---
```

然后执行 `./publish.sh`。

## 本地预览

```bash
.venv/Scripts/python -m mkdocs serve   # Windows
.venv/bin/python -m mkdocs serve       # WSL / Linux
```

打开 http://127.0.0.1:8000
