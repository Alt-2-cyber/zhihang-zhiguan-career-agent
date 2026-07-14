# 职航智管 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可部署、可测试的高校毕业生就业规划与求职事务智能体，完整覆盖学生求职闭环、辅导员管理闭环和可替换的 SF-FastGPT 接入。

**Architecture:** 使用 React 单页应用和 FastAPI 模块化单体，PostgreSQL 保存业务事实，文件存储抽象支持本地目录和 MinIO。Agent Gateway 隔离 SF-FastGPT、超星 AI 与本地演示实现；所有 AI 结果先经过 Pydantic 结构校验和人工确认，再写入业务状态。

**Tech Stack:** React、TypeScript、Vite、Tailwind CSS、TanStack Query、React Hook Form、Zod、ECharts、FastAPI、Pydantic、SQLAlchemy、Alembic、PostgreSQL、PyMuPDF、python-docx、APScheduler、Docker Compose、Pytest、Vitest、Playwright。

---

## 1. 目标文件结构

```text
ai_jiuye/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                 # 配置、安全、异常和数据库会话
│   │   ├── auth/                 # 登录、当前用户和 RBAC
│   │   ├── students/             # 学生档案、就业画像
│   │   ├── plans/                # 求职目标、四周任务
│   │   ├── jobs/                 # 岗位和匹配
│   │   ├── resumes/              # 简历文件、解析和版本
│   │   ├── interviews/           # 模拟面试
│   │   ├── applications/         # 投递流程
│   │   ├── reviews/              # 周复盘
│   │   ├── risks/                # 可解释风险规则
│   │   ├── interventions/        # 辅导员帮扶闭环
│   │   ├── agents/               # Agent 接口、本地实现和 FastGPT 适配
│   │   ├── dashboard/            # 双端聚合视图
│   │   └── audit/                # 审计日志
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app/                  # 路由、请求客户端、会话
│   │   ├── components/           # 通用业务组件
│   │   ├── features/auth/
│   │   ├── features/student/
│   │   ├── features/counselor/
│   │   └── test/
│   └── e2e/
├── deploy/
│   └── nginx.conf
├── scripts/
│   └── verify.ps1
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## 2. 实施任务

### Task 1: 初始化仓库和工程约束

**Files:**
- Create: `.gitignore`
- Create: `.editorconfig`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: 初始化 Git 并建立忽略规则**

忽略 `.env`、虚拟环境、依赖目录、测试缓存、构建产物、上传文件和本地数据库；保留 `.env.example`。

- [ ] **Step 2: 建立统一文本规范**

使用 UTF-8、LF、末尾换行和四空格 Python 缩进；前端使用两空格缩进。

- [ ] **Step 3: 建立环境变量契约**

`.env.example` 明确定义 `APP_ENV`、`SECRET_KEY`、`DATABASE_URL`、`CORS_ORIGINS`、`STORAGE_BACKEND`、`UPLOAD_DIR`、`FASTGPT_BASE_URL`、`FASTGPT_API_KEY`、`FASTGPT_APP_ID` 和演示模式开关。

- [ ] **Step 4: 验证仓库状态**

Run: `git status --short`

Expected: 只显示新增工程文件，不包含 `.env`、缓存或上传内容。

### Task 2: 建立 FastAPI 基础、配置和数据库

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/core/models.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: 写健康检查失败测试**

```python
def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认尚未实现**

Run: `cd backend; python -m pytest tests/test_health.py -q`

Expected: 因 `app.main` 不存在而失败。

- [ ] **Step 3: 实现应用工厂和健康检查**

`create_app()` 注册统一 `/api` 前缀、CORS、异常处理器和健康检查；配置通过 `pydantic-settings` 读取环境变量。

- [ ] **Step 4: 建立数据库会话和基础模型**

使用 SQLAlchemy 2 同步会话；生产默认 PostgreSQL，测试使用临时 SQLite。基础模型提供字符串 UUID、`created_at` 和 `updated_at`。

- [ ] **Step 5: 运行后端基础测试**

Run: `cd backend; python -m pytest tests/test_health.py -q`

Expected: `1 passed`。

### Task 3: 实现身份认证、角色权限和审计

**Files:**
- Create: `backend/app/auth/models.py`
- Create: `backend/app/auth/schemas.py`
- Create: `backend/app/auth/security.py`
- Create: `backend/app/auth/service.py`
- Create: `backend/app/auth/router.py`
- Create: `backend/app/audit/models.py`
- Create: `backend/app/audit/service.py`
- Create: `backend/tests/auth/test_auth.py`
- Create: `backend/tests/auth/test_rbac.py`

- [ ] **Step 1: 写登录和角色隔离测试**

覆盖正确登录、错误密码、过期令牌、学生访问辅导员接口返回 `403`、辅导员访问授权班级成功。

- [ ] **Step 2: 运行认证测试确认失败**

Run: `cd backend; python -m pytest tests/auth -q`

Expected: 因认证路由尚未注册而失败。

- [ ] **Step 3: 实现密码和令牌服务**

使用 Argon2 哈希密码，JWT 只保存用户 ID、角色和过期时间；`get_current_user` 每次从数据库确认用户仍启用。

- [ ] **Step 4: 实现 RBAC 依赖**

定义 `student`、`counselor`、`admin` 三种角色，并提供 `require_roles(...)` 路由依赖。

- [ ] **Step 5: 记录安全相关审计事件**

记录登录成功、登录失败、权限拒绝、数据导出和风险人工确认，不记录明文密码或完整令牌。

- [ ] **Step 6: 运行认证测试**

Run: `cd backend; python -m pytest tests/auth -q`

Expected: 全部通过。

### Task 4: 建立 Agent Gateway 和结构化输出契约

**Files:**
- Create: `backend/app/agents/contracts.py`
- Create: `backend/app/agents/base.py`
- Create: `backend/app/agents/local.py`
- Create: `backend/app/agents/fastgpt.py`
- Create: `backend/app/agents/service.py`
- Create: `backend/tests/agents/test_contracts.py`
- Create: `backend/tests/agents/test_gateway.py`

- [ ] **Step 1: 写结构化契约测试**

验证画像必须包含证据、匹配结果必须包含维度评分与引用、计划任务必须有截止日期和完成标准；缺少字段时 Pydantic 校验必须失败。

- [ ] **Step 2: 运行契约测试确认失败**

Run: `cd backend; python -m pytest tests/agents -q`

Expected: 因契约模型未实现而失败。

- [ ] **Step 3: 定义 Agent 协议**

定义 `analyze_profile`、`build_plan`、`match_job`、`optimize_resume`、`start_interview`、`evaluate_answer` 和 `build_weekly_review` 方法，所有方法返回强类型模型。

- [ ] **Step 4: 实现可复现的本地 Agent**

本地实现根据输入生成确定性演示结果，用于无平台账号时开发和自动化测试；输出明确标记 `provider=local-demo`。

- [ ] **Step 5: 实现 FastGPT HTTP 适配器**

使用 `httpx`、超时、请求 ID 和有限重试调用配置端点；不得记录 API Key 和完整简历正文。将平台输出转换为内部契约，格式错误返回统一 `AgentOutputError`。

- [ ] **Step 6: 运行 Agent 测试**

Run: `cd backend; python -m pytest tests/agents -q`

Expected: 全部通过，测试中不访问外网。

### Task 5: 实现学生档案、简历上传和就业画像

**Files:**
- Create: `backend/app/students/models.py`
- Create: `backend/app/students/schemas.py`
- Create: `backend/app/students/service.py`
- Create: `backend/app/students/router.py`
- Create: `backend/app/resumes/models.py`
- Create: `backend/app/resumes/parser.py`
- Create: `backend/app/resumes/storage.py`
- Create: `backend/app/resumes/router.py`
- Create: `backend/tests/students/test_profiles.py`
- Create: `backend/tests/resumes/test_upload.py`

- [ ] **Step 1: 写档案权限与确认测试**

覆盖学生只能读取和修改自己的档案、辅导员只能读取授权班级、AI 抽取内容在确认前不能成为正式档案。

- [ ] **Step 2: 写文件安全测试**

覆盖 PDF/DOCX 白名单、文件大小上限、随机存储名、路径穿越拒绝和解析失败后的手工文本降级。

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/students tests/resumes -q`

Expected: 因路由尚未实现而失败。

- [ ] **Step 4: 实现档案和简历模型**

学生档案包含专业、技能、经历、偏好和确认版本；简历记录保存文件元数据、解析状态、文本摘要和所属学生。

- [ ] **Step 5: 实现安全上传和解析**

使用 PyMuPDF 解析 PDF、python-docx 解析 DOCX；解析器只返回文本，不直接修改档案。

- [ ] **Step 6: 接入画像 Agent 与确认接口**

画像草稿保存 Agent 证据和模型来源，学生确认后以事务方式更新正式档案。

- [ ] **Step 7: 运行档案与上传测试**

Run: `cd backend; python -m pytest tests/students tests/resumes -q`

Expected: 全部通过。

### Task 6: 实现目标、四周计划、岗位匹配和简历优化

**Files:**
- Create: `backend/app/plans/models.py`
- Create: `backend/app/plans/schemas.py`
- Create: `backend/app/plans/service.py`
- Create: `backend/app/plans/router.py`
- Create: `backend/app/jobs/models.py`
- Create: `backend/app/jobs/schemas.py`
- Create: `backend/app/jobs/service.py`
- Create: `backend/app/jobs/router.py`
- Create: `backend/app/resumes/optimization.py`
- Create: `backend/tests/plans/test_plans.py`
- Create: `backend/tests/jobs/test_matching.py`
- Create: `backend/tests/resumes/test_optimization.py`

- [ ] **Step 1: 写计划和岗位匹配测试**

验证一个主目标、最多两个备选目标、四周任务日期边界、匹配证据必须引用学生或岗位原文，以及跨学生数据不可见。

- [ ] **Step 2: 写简历事实保护测试**

验证优化建议只保存原文、建议文本和理由，未经学生确认不得生成正式简历版本。

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/plans tests/jobs tests/resumes/test_optimization.py -q`

Expected: 因业务服务尚未实现而失败。

- [ ] **Step 4: 实现目标和任务状态机**

任务状态只允许 `pending -> in_progress -> completed` 或进入 `cancelled`；完成任务必须写完成时间。

- [ ] **Step 5: 实现岗位与匹配服务**

保存岗位原始描述和结构化要求；匹配结果包含硬性条件、技能、经历、偏好和发展方向五个维度。

- [ ] **Step 6: 实现简历优化草稿与确认**

确认操作创建不可变版本，保留来源版本、目标岗位和修改记录。

- [ ] **Step 7: 运行相关测试**

Run: `cd backend; python -m pytest tests/plans tests/jobs tests/resumes/test_optimization.py -q`

Expected: 全部通过。

### Task 7: 实现模拟面试、投递看板和每周复盘

**Files:**
- Create: `backend/app/interviews/models.py`
- Create: `backend/app/interviews/schemas.py`
- Create: `backend/app/interviews/service.py`
- Create: `backend/app/interviews/router.py`
- Create: `backend/app/applications/models.py`
- Create: `backend/app/applications/service.py`
- Create: `backend/app/applications/router.py`
- Create: `backend/app/reviews/models.py`
- Create: `backend/app/reviews/service.py`
- Create: `backend/app/reviews/router.py`
- Create: `backend/tests/interviews/test_interviews.py`
- Create: `backend/tests/applications/test_pipeline.py`
- Create: `backend/tests/reviews/test_weekly_review.py`

- [ ] **Step 1: 写面试会话测试**

验证问题关联岗位和简历、追问关联上一个回答、评分只包含内容完整性、岗位相关性、表达结构和证据充分度。

- [ ] **Step 2: 写投递状态机和漏斗测试**

允许 `saved -> applied -> assessment -> interview -> offered`，任意进行中状态可进入 `closed`；拒绝非法回退并保留事件历史。

- [ ] **Step 3: 写周复盘测试**

使用投递事件计算新增投递、回复、笔试、面试和录用数量，改进建议最多三条，学生确认后才能创建新任务。

- [ ] **Step 4: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/interviews tests/applications tests/reviews -q`

Expected: 因模块尚未实现而失败。

- [ ] **Step 5: 实现面试、投递和复盘服务**

所有状态变更使用数据库事务；面试回答和反馈带创建时间、模型来源和所属学生。

- [ ] **Step 6: 运行相关测试**

Run: `cd backend; python -m pytest tests/interviews tests/applications tests/reviews -q`

Expected: 全部通过。

### Task 8: 实现风险规则、辅导干预和双端聚合接口

**Files:**
- Create: `backend/app/risks/models.py`
- Create: `backend/app/risks/rules.py`
- Create: `backend/app/risks/service.py`
- Create: `backend/app/risks/router.py`
- Create: `backend/app/interventions/models.py`
- Create: `backend/app/interventions/service.py`
- Create: `backend/app/interventions/router.py`
- Create: `backend/app/dashboard/router.py`
- Create: `backend/app/dashboard/service.py`
- Create: `backend/tests/risks/test_rules.py`
- Create: `backend/tests/interventions/test_loop.py`
- Create: `backend/tests/dashboard/test_dashboard.py`

- [ ] **Step 1: 写五条风险规则参数化测试**

分别覆盖未定目标、连续无投递、计划多项逾期、多次投递无面试和连续面试未通过；断言等级、事实数值和规则编码。

- [ ] **Step 2: 写干预闭环和班级权限测试**

辅导员只能向授权学生发起任务，学生反馈后辅导员可确认完成；其他班级辅导员访问返回 `403`。

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend; python -m pytest tests/risks tests/interventions tests/dashboard -q`

Expected: 因规则和接口尚未实现而失败。

- [ ] **Step 4: 实现确定性风险引擎**

规则输入只使用任务、投递和面试事实，不读取敏感属性；重复扫描更新同一活动风险，不制造重复事件。

- [ ] **Step 5: 实现干预状态机**

状态为 `assigned`、`acknowledged`、`submitted`、`resolved`、`cancelled`，每次变化记录操作者和时间。

- [ ] **Step 6: 实现学生与辅导员看板聚合接口**

一次请求返回工作台所需计数、近期任务、投递漏斗和风险摘要，避免前端大量串行请求。

- [ ] **Step 7: 运行相关测试**

Run: `cd backend; python -m pytest tests/risks tests/interventions tests/dashboard -q`

Expected: 全部通过。

### Task 9: 建立前端工程、设计系统和认证流程

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/app/api.ts`
- Create: `frontend/src/app/session.tsx`
- Create: `frontend/src/components/AppShell.tsx`
- Create: `frontend/src/features/auth/LoginPage.tsx`
- Create: `frontend/src/features/auth/LoginPage.test.tsx`

- [ ] **Step 1: 写登录和受保护路由测试**

验证未登录访问业务页跳转登录、不同角色进入对应首页、错误凭据显示服务端错误且不保存令牌。

- [ ] **Step 2: 运行前端测试确认失败**

Run: `cd frontend; npm test -- --run`

Expected: 因页面尚未实现而失败。

- [ ] **Step 3: 实现响应式应用外壳**

桌面端使用侧边导航，移动端使用抽屉导航；所有图标按钮提供可访问名称，页面内容不使用嵌套卡片。

- [ ] **Step 4: 实现 API 客户端和会话**

统一处理 `401`、`403`、请求 ID、超时和错误消息；令牌放在内存会话并通过受控持久化恢复。

- [ ] **Step 5: 实现登录页面与角色路由**

学生登录后进入 `/student`，辅导员进入 `/counselor`。

- [ ] **Step 6: 运行前端基础测试**

Run: `cd frontend; npm test -- --run`

Expected: 登录相关测试通过。

### Task 10: 实现学生端完整工作流

**Files:**
- Create: `frontend/src/features/student/StudentDashboard.tsx`
- Create: `frontend/src/features/student/ProfilePage.tsx`
- Create: `frontend/src/features/student/PlanPage.tsx`
- Create: `frontend/src/features/student/JobsPage.tsx`
- Create: `frontend/src/features/student/ResumePage.tsx`
- Create: `frontend/src/features/student/InterviewPage.tsx`
- Create: `frontend/src/features/student/ApplicationBoard.tsx`
- Create: `frontend/src/features/student/ReviewPage.tsx`
- Create: `frontend/src/features/student/student-flow.test.tsx`

- [ ] **Step 1: 写学生主流程测试**

模拟建档、确认画像、接受计划、匹配岗位、确认简历建议、完成一次面试、更新投递状态和确认周复盘。

- [ ] **Step 2: 运行学生流程测试确认失败**

Run: `cd frontend; npm test -- --run src/features/student/student-flow.test.tsx`

Expected: 因学生页面尚未实现而失败。

- [ ] **Step 3: 实现工作台与档案确认**

工作台展示目标、今日任务、投递漏斗和 AI 建议；档案页面以证据对照方式确认抽取内容。

- [ ] **Step 4: 实现计划、岗位和简历页面**

岗位匹配按五维展示证据；简历修改使用原文、建议和理由三列对照，并要求逐项确认。

- [ ] **Step 5: 实现面试、投递和复盘页面**

投递看板使用稳定列宽和可访问移动操作菜单；复盘最多展示三项优先动作。

- [ ] **Step 6: 运行学生流程测试**

Run: `cd frontend; npm test -- --run src/features/student/student-flow.test.tsx`

Expected: 测试通过。

### Task 11: 实现辅导员端完整工作流

**Files:**
- Create: `frontend/src/features/counselor/CounselorDashboard.tsx`
- Create: `frontend/src/features/counselor/StudentListPage.tsx`
- Create: `frontend/src/features/counselor/StudentDetailPage.tsx`
- Create: `frontend/src/features/counselor/InterventionsPage.tsx`
- Create: `frontend/src/features/counselor/counselor-flow.test.tsx`

- [ ] **Step 1: 写辅导员主流程测试**

模拟查看班级指标、按风险原因筛选、打开风险依据、布置任务和确认学生反馈。

- [ ] **Step 2: 运行辅导员流程测试确认失败**

Run: `cd frontend; npm test -- --run src/features/counselor/counselor-flow.test.tsx`

Expected: 因辅导员页面尚未实现而失败。

- [ ] **Step 3: 实现驾驶舱和学生列表**

使用 ECharts 展示投递漏斗和风险原因；数据表支持阶段、等级和原因筛选，风险均显示触发事实。

- [ ] **Step 4: 实现学生详情和帮扶任务**

详情展示目标、任务、事件时间线和审计过的 AI 建议；辅导员可布置、取消和确认任务。

- [ ] **Step 5: 运行辅导员流程测试**

Run: `cd frontend; npm test -- --run src/features/counselor/counselor-flow.test.tsx`

Expected: 测试通过。

### Task 12: 数据迁移、演示数据和定时任务

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial.py`
- Create: `backend/app/core/scheduler.py`
- Create: `backend/app/core/seed.py`
- Create: `backend/tests/test_seed.py`

- [ ] **Step 1: 写幂等演示数据测试**

连续执行两次 seed，用户、岗位、投递和风险数量保持一致；演示账号密码只从环境变量或开发默认值生成。

- [ ] **Step 2: 创建完整初始迁移**

迁移包含所有业务表、外键、唯一约束、查询索引和时间字段。

- [ ] **Step 3: 实现演示数据命令**

生成一名学生、一名辅导员、六个岗位、四周任务、投递记录、面试记录和一条可解释风险事件。

- [ ] **Step 4: 实现调度器**

应用启动时仅在配置启用后注册每日风险扫描，使用数据库锁或唯一运行记录避免多实例重复执行。

- [ ] **Step 5: 验证迁移和 seed**

Run: `cd backend; alembic upgrade head; python -m app.core.seed; python -m pytest tests/test_seed.py -q`

Expected: 迁移成功且测试通过。

### Task 13: 容器化、运行文档和运维检查

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `deploy/nginx.conf`
- Create: `docker-compose.yml`
- Create: `scripts/verify.ps1`
- Modify: `README.md`

- [ ] **Step 1: 构建生产镜像**

后端以非 root 用户运行；前端使用多阶段构建并由 Nginx 提供静态文件和 `/api` 反向代理。

- [ ] **Step 2: 定义 Compose 健康检查**

PostgreSQL 使用 `pg_isready`，后端请求 `/api/health`，前端请求根页面；后端只在数据库健康后启动。

- [ ] **Step 3: 编写一键验证脚本**

脚本检查环境文件、启动容器、等待健康状态、执行后端测试、前端测试和基础 HTTP 冒烟测试，任一失败返回非零退出码。

- [ ] **Step 4: 编写交付文档**

README 说明本地运行、Docker 运行、演示账号、环境变量、FastGPT 配置、数据备份、日志位置和常见故障处理。

- [ ] **Step 5: 验证容器启动**

Run: `docker compose up --build -d`

Expected: 数据库、后端和前端均为 healthy，浏览器可访问应用。

### Task 14: 全链路测试、安全回归和视觉验收

**Files:**
- Create: `frontend/e2e/student-flow.spec.ts`
- Create: `frontend/e2e/counselor-flow.spec.ts`
- Create: `frontend/playwright.config.ts`
- Create: `docs/test-report.md`
- Modify: `scripts/verify.ps1`

- [ ] **Step 1: 编写学生端 E2E**

从登录开始完成档案确认、计划查看、岗位匹配、面试回答和投递状态更新，断言刷新页面后状态仍存在。

- [ ] **Step 2: 编写辅导员端 E2E**

完成风险筛选、依据查看、帮扶任务布置和学生反馈确认，断言未授权班级数据不可访问。

- [ ] **Step 3: 运行完整自动化测试**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`

Expected: 后端、前端、E2E、权限和 HTTP 冒烟测试全部通过。

- [ ] **Step 4: 检查桌面和移动视图**

使用 Playwright 在 1440x900、1024x768 和 390x844 截图；检查文本溢出、遮挡、空白页面、图表尺寸和导航可用性。

- [ ] **Step 5: 检查异常和降级路径**

验证模型超时、格式错误、解析失败、无知识库结果、无权限访问和重复提交均显示可操作错误，且不会产生重复业务记录。

- [ ] **Step 6: 形成测试报告**

记录测试环境、命令、通过数量、关键截图、已知限制和 FastGPT 实际联调状态；未取得官方账号时明确标记本地 Agent 已通过、官方接口待凭据验证。

## 3. 完成定义

- [ ] 学生和辅导员两条主流程均通过自动化 E2E。
- [ ] 后端单元与接口测试覆盖认证、权限、状态机、风险规则和 Agent 输出校验。
- [ ] Docker Compose 可从空环境完成迁移、seed 和启动。
- [ ] 演示数据不含真实个人信息，日志不泄露密码、令牌和完整简历。
- [ ] SF-FastGPT 无凭据时自动使用明确标记的本地演示实现，有凭据时可通过配置切换。
- [ ] README、环境变量样例、数据备份说明和测试报告齐全。
- [ ] 设计文档中的首版必需功能均有对应页面、接口或测试证据。

