# 职航智管

高校毕业生就业规划与求职事务智能体，提供学生求职执行和辅导员就业管理双端闭环。

## 已实现能力

- 学生端：就业画像、四周计划、岗位匹配、简历上传、模拟面试、投递看板和每周复盘。
- 模拟面试：可选开启浏览器摄像头，每 1 秒发送一帧 JPEG 到本地情绪服务；YOLO 负责正脸检测并返回归一化标注框，本地 ViT 表情模型负责表情分类，按人脸出现率、表情一致性和置信度波动生成“表达稳定度（摄像头分析）”训练维度。
- 辅导员端：班级驾驶舱、风险事实、学生列表和帮扶任务闭环。
- Agent：本地确定性演示实现与 SF-FastGPT OpenAI 兼容接口适配。
- 工程能力：JWT/RBAC、审计、Alembic、PostgreSQL、Docker Compose 和自动化测试。

摄像头能力只保存最多 20 条统计结果，不保存原始视频或图片；关闭摄像头、拒绝权限或未检测到清晰人脸时不会生成情绪分数。该维度仅用于表达训练参考，不用于心理诊断或录用判断。

## 环境要求

- Node.js 22 或更高版本
- Python 3.13
- Docker 与 Docker Compose

## 配置

复制 `.env.example` 为 `.env`，并至少修改 `SECRET_KEY`。开发环境可使用 `AGENT_PROVIDER=local`；取得赛事平台凭据后再配置 FastGPT 相关变量。

## Docker 启动

Windows 下可直接双击根目录的 `start-docker.bat`，脚本会检查 Docker、构建容器并在服务就绪后打开浏览器。

```powershell
docker compose up --build -d
```

打开 `http://localhost:8080`。

首次启动情绪服务会在 `emotion_models` 卷中下载 YOLO 人脸模型和 `trpakov/vit-face-expression` 表情模型，模型下载完成后 `emotion` 容器才会变为 healthy。可用以下命令检查：

```powershell
docker compose ps emotion
Invoke-RestMethod http://127.0.0.1:8104/health/ready
```

演示账号：

- 学生：`student_demo` / `Student123!`
- 辅导员：`counselor_demo` / `Counselor123!`

部署到共享或公开环境前必须修改 `.env` 中的密码和 `SECRET_KEY`。

## 本地开发

Windows 下可直接双击根目录的 `start-local.bat`。首次运行会自动创建 Python 环境、安装缺失的依赖、初始化数据库，然后分别打开前后端终端和浏览器。

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.core.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
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
