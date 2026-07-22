---
kind: frontend_style
name: 内嵌单页应用与极简 CSS 变量主题
category: frontend_style
scope:
    - '**'
source_files:
    - frontend/index.html
    - frontend/server.py
---

本仓库的前端采用“零构建、零依赖”的极简方案：一个由 FastAPI 直接返回的单页 HTML（`frontend/index.html`），所有样式以 `<style>` 标签内联，通过 CSS 自定义属性（CSS Variables）集中管理设计令牌，JS 逻辑同样内联在页面底部。后端 `frontend/server.py` 仅作为 API 网关，不渲染模板，也不引入任何前端框架或打包工具。

**1. 使用的系统/方法**
- 纯原生 HTML + CSS + JavaScript，无任何 UI 组件库、CSS 预处理器或构建步骤。
- 使用 CSS 自定义属性（`:root { --bg-main, --accent, ... }`）作为全局设计令牌，实现浅色主题与视觉一致性。
- 响应式策略基于 Flexbox/Grid + 少量 `@media print` 打印适配，未使用媒体查询做断点适配。
- 图标全部以内联 SVG 形式嵌入，避免外部字体/图标包依赖。

**2. 关键文件**
- `frontend/index.html` — 唯一的前端入口，包含完整的 HTML 结构、内联 CSS 与 JS 逻辑。
- `frontend/server.py` — FastAPI 服务，提供 `/api/*` REST 接口并返回 `index.html`。

**3. 架构与约定**
- **布局模型**：左侧可折叠侧边栏（`#sidebar`）+ 右侧主内容区（`main`），通过切换 `hidden` / `show` 类名在 chat/paper/library 三个视图间切换。
- **主题系统**：所有颜色、边框、背景色均通过 `--bg-*`、`--text-*`、`--border-*`、`--accent` 等变量定义，新增配色只需修改 `:root` 块。
- **组件风格**：卡片（`.paper-card`）、消息气泡（`.msg.user/.msg.bot`）、按钮（`.btn-primary`）、输入框等均有统一圆角（8–16px）、边框（`var(--border-subtle)`）与 hover 过渡（0.15s）。
- **交互模式**：无路由框架，通过 `go('chat'|'paper'|'library')` 函数控制 DOM 可见性；历史会话、收藏、试卷等均通过 `fetch('/api/...')` 与后端通信。
- **打印适配**：`@media print` 隐藏交互控件、展开题目详情、调整颜色为黑白打印友好。

**4. 开发者应遵循的规则**
- 新增样式一律写入 `index.html` 的 `<style>` 块中，优先复用现有 CSS 变量，不要硬编码颜色值。
- 新增 UI 组件时保持命名前缀一致（如 `.sb-*` 侧边栏、`.msg-*` 消息、`.pv-*` 出题视图、`.lib-*` 文件库）。
- 图标使用内联 SVG，尺寸统一 16–24px，颜色通过 `currentColor` 继承文本色。
- 交互逻辑集中在页面底部 `<script>` 中，按功能域分组（聊天、出题、收藏、历史会话），避免全局污染。
- 如需深色主题，可在 `:root` 下覆盖变量或通过 `color-scheme` 切换，不建议拆分多份 CSS 文件。