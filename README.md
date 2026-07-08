# KevinHu

一个极简静态博客，文章源文件放在 `docs/blog/posts`，通过 `build.py` 生成到 `site`。

## 本地预览

```powershell
python build.py
python -m http.server 8000 -d site
```

然后访问：

```text
http://127.0.0.1:8000
```

## 写文章

在 `docs/blog/posts` 下新增 Markdown 文件，保留类似下面的 front matter：

```markdown
---
title: 文章标题
draft: false
date: 2026-01-01
slug: post-slug
categories:
  - Engineering
---
```

`<!-- more -->` 前面的内容会作为首页摘要。
