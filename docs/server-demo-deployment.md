# 低资源服务器演示版

## 部署范围

当前演示站点：`http://111.228.30.194`。服务器部署目录：`/opt/career-server-demo`。

服务器演示版以低内存 VPS 为目标，包含 Nginx、FastAPI、PostgreSQL/pgvector、Redis 和一个轻量任务 Worker。Agent 使用外部模型 API；部署包不启动本地 OCR、向量、语音和视觉模型容器，也不使用假响应代替这些能力。Docker 镜像默认经由 `docker.1panel.live` 拉取，Python 依赖使用阿里云 PyPI 镜像，以适配该云主机到 Docker Hub/PyPI 官方站点较慢或超时的网络；更换镜像源时需同步调整 `backend/Dockerfile.server-demo` 和 Compose 中的镜像名。

前端从 `/api/ai/capabilities` 读取实际部署模式，在所有业务页显示演示版说明。后端拒绝未部署的异步任务，并将不可用能力从 Agent 工具目录中过滤掉。在线模型 API 未配置、网络不可达或额度不足时，Agent 会如实报错，不回退到本地演示规则。

## 可以演示

- 学生和辅导员登录，以及演示数据库中的业务记录。
- 就业画像、计划、岗位、投递状态、班级驾驶舱和帮扶流程。
- 在线模型 API 可用时的持久对话、多 Agent 规划、内部业务工具调用和安全写操作确认。
- 公开岗位网页检索。结果来自公开网页搜索，需要打开来源核验；不是稳定招聘平台 API，也不自动投递。
- 对可提取文本的 DOCX 和 PDF 做基础文本解析；支持手工补录文本。
- 文字模拟面试、模型评分与建议；数字人问题保留文字显示。

## 此版本不具备

| 能力 | 演示版状态 | 原因与影响 |
| --- | --- | --- |
| 扫描件 PDF OCR | 不可用 | 未部署 PaddleOCR；可提取文本的 PDF 仍可由基础解析器尝试读取，纯扫描件需改用可复制文本的文件或手工录入 |
| BGE-M3 语义检索 | 不可用 | 未部署 embedding 服务；Agent 不提供简历、课程或知识库的向量召回，工具目录不提供 `knowledge.search` |
| 语音输入 ASR | 不可用 | 未部署 FunASR；使用文字输入 |
| 语音朗读 TTS | 不可用 | 未部署 MeloTTS；面试题只显示文字 |
| 摄像头表情分析 | 不可用 | 未部署 YOLO 和表情模型；不会采集摄像头画面或生成情绪/表达稳定度结果 |
| 对话附件解析 | 不可用 | OCR/向量服务缺失，附件入口会禁用，后端也拒绝附件任务 |
| 完整版独立服务拓扑 | 不可用 | 演示版不运行模型容器、对象存储、Prometheus 和 OpenTelemetry |

上表描述的是当前服务器部署能力，不代表完整项目代码删除了这些模块。切回全量 Compose 并满足模型运行的 CPU/GPU 和磁盘条件后，才可启用这些本地服务。

## 资源建议

该配置针对约 2 GiB 内存的小型服务器，容器设置了内存上限。数据库和文本 Agent 适合少量并发演示，不适合生产负载。模型服务不在此机器运行，因此演示版需要可访问且有有效额度的在线模型 API。

全量本地 AI 服务建议使用至少 16 GiB 内存、100 GiB SSD，并按 FunASR/YOLO 部署选择 GPU；显存 6 GiB 是项目原配置的起点，不保证所有模型同时高吞吐运行。

## 本地准备静态前端

在项目根目录执行：

```powershell
cd frontend
$env:VITE_DEPLOYMENT_MODE = 'server-demo'
npm ci
npm run build
```

产物位于 `frontend/dist`。它包含全站演示版能力提示；开发用的完整前端构建不设置此环境变量。

## 服务器配置

1. 安装 Docker Engine 和 Docker Compose 插件。
2. 上传项目的 `backend/app`、`backend/alembic`、`backend/Dockerfile.server-demo`、`backend/pyproject.toml`、`backend/alembic.ini`、`frontend/dist`、`deploy/nginx.server-demo.conf`、`docker-compose.server-demo.yml`。
3. 从 `.env.server-demo.example` 复制为 `.env.server-demo`，设置高强度随机 `SECRET_KEY`、`POSTGRES_PASSWORD`、Fernet `DATA_ENCRYPTION_KEY`、学生/辅导员演示密码，以及可用的 `DEEPSEEK_API_KEY`。不要把真实密钥提交到 Git 或截图。
4. 将 `PUBLIC_HOST` 设置为服务器 IP 或域名。安全组/云防火墙需放行 TCP 80；当前未配置 HTTPS，正式公开访问前应绑定域名并启用 TLS。
5. 从部署目录启动：

```bash
docker compose --env-file .env.server-demo -f docker-compose.server-demo.yml up -d --build
docker compose --env-file .env.server-demo -f docker-compose.server-demo.yml ps
```

首次启动会运行 Alembic 迁移和脱敏演示数据初始化。登录账号为 `student_demo` 和 `counselor_demo`，密码使用 `.env.server-demo` 中设置的对应值。

## 运维命令

```bash
docker compose --env-file .env.server-demo -f docker-compose.server-demo.yml logs -f backend worker
docker compose --env-file .env.server-demo -f docker-compose.server-demo.yml restart backend worker frontend
docker compose --env-file .env.server-demo -f docker-compose.server-demo.yml down
```

不要对已有演示数据库执行 `down -v`，该命令会删除数据库、Redis 和上传文件卷。

Worker 不提供 HTTP 健康端点，因此演示 Compose 不套用后端的 HTTP 健康检查。任务是否执行成功以 AI 任务状态、Agent 执行记录和 Worker 日志为准。

## 评审说明

推荐在答辩中主动说明这是低资源服务器演示部署：在线 Agent 和业务工作流是真实调用/真实数据库；本地 OCR、BGE-M3、ASR/TTS、YOLO 和相关异步能力未启动。展示时可以用已有脱敏业务记录和文字面试，不能将服务未部署描述成模型已运行。
