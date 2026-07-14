# 职航智管测试报告

## 测试环境

- 日期：2026-07-14
- 操作系统：Windows
- Node.js：24.11.1
- Python：3.13.14
- Docker CLI / Engine：29.1.5
- 浏览器：Playwright Chromium 149
- Agent 模式：`local-demo`
- 本地数据库：SQLite，通过 Alembic 从空库初始化

## 自动化结果

| 检查项 | 命令 | 结果 |
| --- | --- | --- |
| 后端静态检查 | `ruff check app tests` | 通过，0 个问题 |
| 后端测试 | `pytest -q` | 34 通过，0 失败 |
| 前端静态检查 | `npm run lint` | 通过，0 个问题 |
| 前端组件测试 | `npm test -- --run` | 4 通过，0 失败 |
| 前端生产构建 | `npm run build` | 通过，无大包警告 |
| 浏览器 E2E | `npm run e2e` | 4 通过，0 失败 |
| Compose 配置 | `docker compose config --quiet` | 通过 |
| Python 依赖完整性 | `python -m pip check` | 通过，无损坏依赖 |
| 前端生产依赖审计 | `npm audit --omit=dev` | 通过，0 个已知漏洞 |

## 覆盖范围

- 登录、JWT、密码错误、角色权限和登录审计。
- Agent 输出结构、画像证据、岗位五维完整性和 FastGPT 异常输出。
- 画像确认、简历文件安全、四周计划、岗位匹配和简历版本确认。
- 模拟面试、投递阶段状态机、不可变事件和每周漏斗复盘。
- 五类可解释风险规则、班级权限和帮扶任务双端闭环。
- Alembic 模型完整性、幂等演示数据和定时任务开关。
- 桌面与 390×844 移动端登录、岗位匹配、风险展示及横向溢出。

## 浏览器实测

真实浏览器完成了以下操作：

1. 学生登录并查看工作台。
2. 选择数据分析师岗位并完成五维匹配，显示匹配分数和原文证据。
3. 辅导员登录并查看“连续 14 天无投递记录”的风险事实。
4. 学生提交“完成岗位筛选”的帮扶反馈。
5. 辅导员查看反馈并确认任务完成。
6. 移动端打开抽屉导航，页面 `scrollWidth` 与 `clientWidth` 均为 390。
7. 最终浏览器控制台为 0 错误、0 警告。

截图：

- `docs/test-artifacts/student-dashboard-desktop.png`
- `docs/test-artifacts/counselor-dashboard-desktop.png`
- `docs/test-artifacts/counselor-dashboard-mobile.png`

## 容器验证状态

Docker Desktop 引擎能够启动，Compose 配置解析通过。执行 `docker compose up --build -d` 时，当前网络无法连接 `registry-1.docker.io:443`，因此不能拉取 `postgres:17-alpine` 等基础镜像，容器构建未能在本机完成。

该限制发生在镜像拉取阶段，未进入项目 Dockerfile 构建。网络恢复后执行以下命令即可重新验证：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## 外部平台状态

- SF-FastGPT：HTTP 适配器和 MockTransport 测试已通过；尚无赛事账号，未进行官方环境实调。
- 超星 AI 能力中心：尚无账号，未进行模型接口联调。
- 百川云璟：尚无账号，当前演示数据为项目自带脱敏数据。
- 图像概念生成：当前会话未提供内置图像生成工具，未生成独立 UI 概念图；最终界面已通过 Playwright 截图和 `view_image` 人工检查。

## 视觉验收记录

| 检查点 | 结果 |
| --- | --- |
| 信息架构 | 学生与辅导员使用独立导航和工作台，首屏直接进入业务 |
| 排版密度 | 标题、指标、任务、表格和状态层级清晰，无营销式大标题 |
| 颜色 | 白色与浅灰为主，青绿用于操作，橙色用于风险，未使用单一蓝紫主题 |
| 容器 | 页面不使用嵌套卡片，统计条、列表和业务面板边界稳定 |
| 图标 | 功能按钮和导航使用 Lucide 图标，移动端提供可访问名称 |
| 响应式 | 1440×900 与 390×844 均无文本遮挡，移动端横向溢出已修复 |

## 已知限制

- 官方赛事平台的最终请求参数可能与当前 OpenAI 兼容接口存在差异，取得账号后需要依据培训文档调整适配器。
- 首版文件存储使用受控本地目录和持久化卷，尚未实现 MinIO 驱动。
- 风险规则不使用敏感属性，也不预测就业成功率；辅导员需人工确认风险和干预动作。
