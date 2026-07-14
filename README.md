# 职航智管

高校毕业生就业规划与求职事务智能体，提供学生求职执行和辅导员就业管理双端闭环。

## 已实现能力

- 学生端：就业画像、四周计划、岗位匹配、简历上传、模拟面试、投递看板和每周复盘。
- 辅导员端：班级驾驶舱、风险事实、学生列表和帮扶任务闭环。
- Agent：本地确定性演示实现与 SF-FastGPT OpenAI 兼容接口适配。
- 工程能力：JWT/RBAC、审计、Alembic、PostgreSQL、Docker Compose 和自动化测试。

## 环境要求

- Node.js 22 或更高版本
- Python 3.13
- Docker 与 Docker Compose

## 配置

复制 `.env.example` 为 `.env`，并至少修改 `SECRET_KEY`。开发环境可使用 `AGENT_PROVIDER=local`；取得赛事平台凭据后再配置 FastGPT 相关变量。

## Docker 启动

```powershell
docker compose up --build -d
```

打开 `http://localhost:8080`。

演示账号：

- 学生：`student_demo` / `Student123!`
- 辅导员：`counselor_demo` / `Counselor123!`

部署到共享或公开环境前必须修改 `.env` 中的密码和 `SECRET_KEY`。

## 本地开发

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.core.seed
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

开发地址为 `http://localhost:5173`，Vite 会将 `/api` 转发到 `http://localhost:8000`。

## FastGPT 接入

设置以下变量后将 `AGENT_PROVIDER` 改为 `fastgpt`：

```text
FASTGPT_BASE_URL=https://your-fastgpt-host/api
FASTGPT_API_KEY=your-key
FASTGPT_APP_ID=your-app-id
```

平台输出必须符合 `backend/app/agents/contracts.py` 中的结构化契约。凭据不会写入日志。

## 自动验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

仅运行代码检查和测试：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1 -SkipContainers
```

## 数据与日志

- PostgreSQL 数据保存在 Compose 卷 `postgres_data`。
- 上传文件保存在 Compose 卷 `uploads_data`。
- 数据库备份可使用 `docker compose exec db pg_dump -U career career > career-backup.sql`。
- 容器日志使用 `docker compose logs -f backend` 查看，日志不记录密码、令牌或完整简历正文。

详细产品设计与实施记录位于 `docs/superpowers/`。
