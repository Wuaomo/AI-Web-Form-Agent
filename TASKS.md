# TASKS.md

> 用这个文件追踪开发进度。  
> 每次只做一个小功能，不要一次性让 Codex 做完整项目。

---

## Milestone 1：项目初始化

- [x] 创建项目目录 `ai-web-form-agent`
- [x] 创建 `backend/`
- [x] 创建 `frontend/`
- [x] 创建 `docs/`
- [x] 创建 `AGENT_RULES.md`
- [x] 创建 `TASKS.md`
- [x] 初始化 Git 仓库

---

## Milestone 2：本地测试表单

- [x] 创建 `backend/examples/register.html`
- [x] 表单包含 full name
- [x] 表单包含 email
- [x] 表单包含 university
- [x] 表单包含 major
- [x] 表单包含 phone
- [x] 表单包含 LinkedIn
- [x] 表单包含 GitHub
- [x] 表单包含 textarea，例如 self introduction
- [x] 表单包含 select，例如 education level
- [x] 表单包含 checkbox，例如 agree terms
- [x] 表单包含 submit button
- [x] 可以在浏览器中打开测试表单

---

## Milestone 3：FastAPI 后端骨架

- [ ] 创建 `backend/app/main.py`
- [ ] 创建 `backend/app/schemas.py`
- [ ] 创建 `backend/requirements.txt`
- [ ] 实现 `GET /health`
- [ ] 实现 `POST /run-task`
- [ ] `/run-task` 可以接收 url、task、profile
- [ ] 可以打开 `http://localhost:8000/docs`

---

## Milestone 4：Playwright 浏览器控制

- [ ] 安装 Playwright
- [ ] 安装 Chromium browser
- [ ] 创建 `browser_executor.py`
- [ ] 实现打开 URL
- [ ] 实现等待页面加载
- [ ] 实现截图保存
- [ ] `/run-task` 可以返回截图路径

---

## Milestone 5：表单字段提取

- [ ] 创建 `form_extractor.py`
- [ ] 提取 input
- [ ] 提取 textarea
- [ ] 提取 select
- [ ] 提取 checkbox
- [ ] 提取 radio
- [ ] 提取 button
- [ ] 获取 label
- [ ] 获取 placeholder
- [ ] 获取 name
- [ ] 获取 id
- [ ] 生成 selector
- [ ] 创建 `POST /extract-fields`
- [ ] 本地测试表单可提取出所有字段

---

## Milestone 6：规则版字段匹配

- [ ] 创建 `field_mapper.py`
- [ ] 实现 email 匹配
- [ ] 实现 name 匹配
- [ ] 实现 university/school 匹配
- [ ] 实现 major 匹配
- [ ] 实现 phone/mobile 匹配
- [ ] 输出 fill_actions
- [ ] 不接 LLM 也能完成字段映射

---

## Milestone 7：自动填写表单

- [ ] 实现 `fill_form(url, fill_actions)`
- [ ] 支持 input fill
- [ ] 支持 textarea fill
- [ ] 支持 checkbox check
- [ ] 支持 radio check
- [ ] 支持 select option
- [ ] 每一步生成 action log
- [ ] 填写完成后保存截图
- [ ] 不点击 submit
- [ ] `/run-task` 可以完整执行：打开网页 -> 提取字段 -> 匹配字段 -> 填写表单

---

## Milestone 8：提交前安全暂停

- [ ] 创建 `safety_checker.py`
- [ ] 检测 submit
- [ ] 检测 send
- [ ] 检测 confirm
- [ ] 检测 pay
- [ ] 检测 delete
- [ ] 检测 purchase
- [ ] 检测 register
- [ ] 检测 apply
- [ ] 如果发现敏感按钮，返回 `waiting_for_approval`
- [ ] 日志中说明暂停原因
- [ ] 不自动提交表单

---

## Milestone 9：LLM 字段匹配

- [ ] 创建 OpenAI/Gemini API 配置
- [ ] 实现 `map_fields_with_llm(fields, profile)`
- [ ] Prompt 要求 LLM 只输出 JSON
- [ ] 校验 LLM 返回结果
- [ ] LLM 失败时 fallback 到规则匹配
- [ ] 禁止 LLM 输出 submit/click 动作
- [ ] 对不同表单 label 进行测试

---

## Milestone 10：React 前端

- [ ] 创建 React + Vite 项目
- [ ] 创建 `TaskForm.jsx`
- [ ] 创建 `ActionLogs.jsx`
- [ ] 创建 `ScreenshotViewer.jsx`
- [ ] 创建 `ApprovalPanel.jsx`
- [ ] 创建 `api.js`
- [ ] 前端可以输入 URL
- [ ] 前端可以输入 task
- [ ] 前端可以输入 profile JSON
- [ ] 前端可以调用 `POST /run-task`
- [ ] 前端可以展示 logs
- [ ] 前端可以展示 screenshot
- [ ] 前端可以展示 Confirm Submit 按钮
---

## Milestone 11：项目包装

- [x] 写 README.md
- [ ] 写 docs/architecture.md
- [ ] 写 docs/demo-flow.md
- [ ] 截图
- [ ] 录制 1-2 分钟 Demo 视频
- [ ] 整理 GitHub 仓库
- [ ] 写简历 bullet points

---

## 最小可交付版本 MVP

完成这些就可以放进简历：

- [ ] FastAPI 后端
- [ ] Playwright 控制浏览器
- [ ] 动态提取表单字段
- [ ] 规则或 LLM 字段匹配
- [ ] 自动填写表单
- [ ] 执行日志
- [ ] 截图
- [ ] 提交前暂停
- [ ] 简单 React 页面
