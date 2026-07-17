# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal blog ("DevHiker's Blog", https://riohu.com) built with **MkDocs Material** and its built-in blog plugin. Content is primarily in Chinese. Deployed to GitHub Pages via a custom domain (`docs/CNAME`).

## Commands

```bash
# Install dependencies (pinned; guards against the announced MkDocs 2.0 breaking changes)
pip install -r requirements.txt

# Local dev server with live reload (http://127.0.0.1:8000)
mkdocs serve

# Production build (outputs to site/)
mkdocs build
```

There are no tests or linters. Verify changes by running `mkdocs serve` and checking pages render.

## Deployment

Pushing to `main` triggers `.github/workflows/publish.yml`, which runs `mkdocs gh-deploy --force` to publish to the `gh-pages` branch. The workflow fails if `docs/CNAME` is missing — never delete it. The `site/` directory is a local build artifact, not the deployed output.

The `social` plugin (share-card images) is gated behind `enabled: !ENV [CI, false]` — it only runs in CI, where the workflow installs the required system libraries (cairo etc.). Don't enable it unconditionally; local Windows environments lack the native deps.

## Architecture

- `mkdocs.yml` — single source of config: theme (light/dark palette toggle, `language: zh`), plugins (blog, rss, search, autorefs, tags, social), nav (About + Blog + 标签).
- `docs/index.md` — homepage content (name, one-line bio, links) rendered through `template: home.html` as a vertically centered card. Keep it minimal — no post lists or extra sections.
- `docs/templates/` — the **active** theme override directory (`theme.custom_dir` in mkdocs.yml). Contains `main.html` (base override; JSON-LD for posts), `home.html` (homepage template; centers `page.content`), `404.html` (custom error page), and `partials/comments.html` (Giscus comments with palette theme-sync, injected on all non-homepage pages).
- `docs/blog/posts/` — blog posts. `docs/blog/.authors.yml` defines authors referenced in post front matter.
- `docs/blog/tags.md` — tags index page; the `<!-- material/tags -->` marker is replaced by the tags plugin.
- `docs/css/extra.css` — custom styles loaded via `extra_css`. Uses Material CSS variables (`--md-default-fg-color--*`) so both light and dark (`slate`) schemes work — avoid hardcoded colors.

## Blog Post Conventions

Posts in `docs/blog/posts/*.md` use this front matter:

```yaml
---
title: 文章标题
draft: false          # blog plugin has draft: true, so drafts render in local preview
authors: [huyi]       # key from docs/blog/.authors.yml
date: 2025-06-29
slug: post-slug       # post URL is /blog/<slug>/ (post_url_format: "{slug}")
categories:
  - 随笔
tags:
  - Java              # shown on the post and aggregated on docs/blog/tags.md
---
```

The post body starts with a summary paragraph ending in `<!-- more -->` (excerpt separator), followed by an H1 title.
