# 职航智管

高校毕业生就业规划与求职事务智能体，提供学生求职执行和辅导员就业管理双端闭环。

## 当前状态

项目正在按 [实施计划](docs/superpowers/plans/2026-07-14-ai-employment-agent-implementation.md) 开发。首版采用 React、FastAPI、PostgreSQL 和可替换的 SF-FastGPT Agent Gateway。

## 环境要求

- Node.js 22 或更高版本
- Python 3.13
- Docker 与 Docker Compose

## 配置

复制 `.env.example` 为 `.env`，并至少修改 `SECRET_KEY`。开发环境可使用 `AGENT_PROVIDER=local`；取得赛事平台凭据后再配置 FastGPT 相关变量。

完整的本地运行、容器部署、测试和数据备份说明将在各模块完成后持续补充。

