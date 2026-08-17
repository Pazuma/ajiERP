---
title: Product Requirements
---

# frappe_docker 产品需求文档

版本：v1.1

文档状态：基于 2026-08-17 仓库实现审查整理。本文描述当前仓库已经提供的能力、使用约束和建议演进方向，不等同于所有能力默认启用。

## 1. 产品定位

`frappe_docker` 是 Frappe / ERPNext 的容器化交付系统，面向部署、开发、测试、发布和运维场景，提供可复用的 Docker 镜像、Compose 编排、开发容器、集成测试和文档。

它不是业务应用本身，而是 Frappe 生态的基础设施产品。

## 2. 产品目标

- 让用户可以快速启动 Frappe / ERPNext
- 让生产部署可重复、可升级、可回滚
- 让自定义 app 可以在构建期安全注入
- 让本地开发、调试、测试、发布走同一套基础设施思路
- 让运维和贡献者能通过文档和 CI 维持一致性

## 2.1 要解决的问题

Frappe/ERPNext 的运行时由 Web、后台任务、调度器、WebSocket、数据库和 Redis 等多个进程组成。不同团队如果各自维护镜像、启动命令和部署脚本，容易出现以下问题：

- 开发环境和生产环境使用不同的启动方式，问题难以复现
- 自定义 app 在容器运行后临时安装，重建或扩容时容易丢失
- 数据库、Redis、代理和 HTTPS 配置分散，部署组合不清晰
- 镜像构建、集成测试和发布缺少统一入口
- 站点数据、assets、备份和应用源码的持久化边界不明确

本项目通过镜像、Compose、override、开发容器、测试和文档，把这些基础设施能力收敛为可复用的交付链路。

## 3. 目标用户

### 3.1 运维/部署用户

需要在单机或多机环境中部署 ERPNext、CRM、Helpdesk 或自定义 Frappe 应用。

### 3.2 开发用户

需要在本地容器中开发 Frappe app、调试后端、前端、worker、scheduler 和 websocket。

### 3.3 平台维护者

负责构建镜像、发布版本、维护文档、修复部署问题和升级依赖。

### 3.4 下游应用团队

希望复用 `frappe_docker` 的镜像构建链路，产出自己的应用镜像。

## 4. 现有产品模块

### 4.1 基础运行编排

`compose.yaml` 提供核心服务骨架：

- `configurator`
- `backend`
- `frontend`
- `websocket`
- `queue-short`
- `queue-long`
- `scheduler`

职责是把 Frappe 运行时拆成标准进程，并通过 volume、环境变量和依赖关系串起来。

### 4.2 数据与中间件模块

通过 overrides 接入：

- MariaDB
- PostgreSQL
- Redis cache
- Redis queue
- Docker secret 密码

### 4.3 访问与网络模块

支持多种入口方式：

- 直连 8080
- Traefik HTTP
- Traefik HTTPS
- 独立 Traefik dashboard
- nginx-proxy
- nginx-proxy + acme-companion
- 自定义域名转发
- 多 bench 网络隔离

### 4.4 镜像构建模块

提供四类镜像：

- `bench` 开发镜像
- `production` 官方 ERPNext 运行镜像
- `custom` 自定义 app 运行镜像
- `layered` 基于预构建层的快速镜像

### 4.5 开发环境模块

提供：

- Devcontainer 示例
- VS Code 调试配置
- bench 初始化脚本
- 示例 apps.json
- 本地开发用 MariaDB / Redis / 端口转发

### 4.6 测试与质量模块

提供 pytest 集成测试，覆盖：

- 核心服务连接
- 首页和 API 连通
- assets 访问
- 文件安全头
- 备份到 S3
- HTTPS override
- ERPNext 行为
- PostgreSQL 建站

### 4.7 文档模块

提供从入门到生产、开发、迁移、排障的完整文档站。

### 4.8 CI/CD 模块

提供：

- lint
- bench 镜像构建
- core 镜像构建测试
- core 镜像发布
- app 镜像构建
- 文档站发布
- pre-commit 自动更新
- stale issue/PR 维护

## 4.9 能力状态说明

| 状态 | 含义 |
| --- | --- |
| 已实现 | 仓库已有对应文件、脚本或工作流，可以按文档使用 |
| 组合实现 | 能力由基础 Compose 与一个或多个 override 组合提供，不是默认单独开启 |
| 测试覆盖 | 当前主要通过集成测试验证，仍需结合实际部署参数确认 |
| 待完善 | 仓库已有部分实现或入口，但文档、边界或自动化仍不完整 |

当前项目的核心价值是“提供可组合的交付组件”，因此部署者需要先选择拓扑，再组合对应的 Compose 文件和环境变量。

## 5. 核心使用场景

### 场景 A: 快速体验

用户希望在本地几分钟内启动 ERPNext 试用。

### 场景 B: 生产部署

用户希望使用 Docker Compose 在单机或多机环境稳定部署。

### 场景 C: 自定义应用交付

用户希望把自定义 app 作为镜像的一部分构建并发布。

### 场景 D: 本地开发

用户希望在容器中完成代码编辑、调试、数据库访问和前端联调。

### 场景 E: 平台升级

维护者需要升级 Frappe / ERPNext / Python / Node / Debian 基础镜像并保持兼容。

## 6. 功能需求

### 6.1 必须支持的功能

1. 启动核心 Frappe 服务
2. 支持数据库和 Redis 配置注入
3. 支持站点创建和迁移
4. 支持文件上传、assets、public files
5. 支持 background job 和 scheduler
6. 支持 websocket
7. 支持 HTTPS 和反向代理
8. 支持自定义 app 镜像构建
9. 支持开发调试环境
10. 支持自动化测试
11. 支持文档站发布

### 6.2 重要增强能力

1. 支持 PostgreSQL
2. 支持多 bench
3. 支持自动迁移
4. 支持定时备份
5. 支持 Docker secret
6. 支持下游 app 复用构建流程

### 6.3 功能优先级与当前状态

| 编号 | 功能需求 | 优先级 | 当前状态 | 主要实现位置 |
| --- | --- | --- | --- | --- |
| FR-001 | 启动 Frappe 核心进程并提供 HTTP 访问 | P0 | 已实现 | `compose.yaml`, `resources/core/` |
| FR-002 | 配置数据库、Redis、Socket.IO 和站点公共配置 | P0 | 已实现 | `configurator`, `overrides/compose.*` |
| FR-003 | 支持站点创建、迁移和应用安装 | P0 | 组合实现 | `pwd.yml`, `development/installer.py`, `compose.migrator.yaml` |
| FR-004 | 支持短队列、长队列和 scheduler | P0 | 已实现 | `compose.yaml` |
| FR-005 | 支持上传文件、public files、assets 和安全响应头 | P0 | 已实现 | `resources/core/nginx/`, entrypoint |
| FR-006 | 支持 WebSocket/Socket.IO 实时通信 | P0 | 已实现 | `websocket`, Nginx 配置 |
| FR-007 | 支持 MariaDB、PostgreSQL 和外部数据库 | P0 | 组合实现 | `overrides/`, `example.env` |
| FR-008 | 支持内置或外部 Redis cache/queue | P0 | 组合实现 | `overrides/`, `example.env` |
| FR-009 | 支持直连、Traefik、nginx-proxy 和 HTTPS | P1 | 组合实现 | `overrides/compose.*proxy*.yaml` |
| FR-010 | 支持自定义 app 在构建期进入镜像 | P0 | 已实现 | `images/custom/`, `images/layered/` |
| FR-011 | 支持 Bench 开发镜像和 Devcontainer | P0 | 已实现 | `images/bench/`, `devcontainer-example/` |
| FR-012 | 支持 Docker Compose 集成测试 | P0 | 已实现 | `tests/` |
| FR-013 | 支持多架构构建和镜像发布 | P1 | 已实现 | `docker-bake.hcl`, `.github/workflows/` |
| FR-014 | 支持自动迁移和定时备份 | P1 | 组合实现 | `compose.migrator.yaml`, `compose.backup-cron.yaml` |
| FR-015 | 支持多 bench、共享代理和自定义域名 | P1 | 组合实现 | `compose.multi-bench*.yaml`, `compose.custom-domain*.yaml` |
| FR-016 | 提供完整部署、开发、迁移和排障文档 | P0 | 待完善 | `docs/` |

P0 表示系统基本可用和交付链路必须具备的能力，P1 表示生产增强或特定拓扑能力。优先级是产品管理分类，不代表对应实现一定默认开启。

## 7. 非功能需求

### 7.1 可移植性

- 支持 amd64 和 arm64
- 支持 Linux、macOS、Windows 开发场景
- 支持单机和多机部署拓扑

### 7.2 可重复性

- 镜像构建应可复现
- 运行时不依赖人工修改容器内部状态
- app 应在构建期进入镜像

### 7.3 可维护性

- Compose override 组合清晰
- 环境变量有统一参考
- 文档和实现保持同步

### 7.4 安全性

- 支持 secret 文件
- 支持 HTTPS
- 支持安全头
- 避免把站点私有文件写入代码仓库

### 7.5 稳定性

- 服务间依赖顺序明确
- 支持健康检查和重试
- 支持自动迁移与备份

### 7.6 可观测性与可运维性

- 各核心进程应能通过容器日志识别启动失败、连接失败和迁移失败
- 部署文档应说明服务状态、日志、站点访问和数据库连接的基本检查方式
- 备份、迁移和 HTTPS 等可选能力应有明确的成功判定和失败排查路径
- 生产环境应由外部监控系统负责资源、容器和业务可用性监控；本项目不替代完整监控平台

## 8. 数据与状态边界

### 8.1 应持久化的数据

- `sites`
- 数据库 volume
- 需要保留的队列数据
- 备份数据

### 8.2 不应持久化的数据

- 应用源码
- 构建产物
- 运行时 assets 实体内容
- 临时日志和缓存

## 9. 成功标准

- 用户能用一套标准文件启动生产或 demo 环境
- 用户能在不改源码的情况下切换数据库和代理方案
- 用户能为自定义 app 构建镜像
- 测试和发布流程可以自动化执行
- 文档能覆盖主要使用路径

## 9.1 用户故事与验收标准

### US-001 快速启动体验环境

作为首次使用者，我希望使用单个 Compose 文件启动 ERPNext，以便快速验证系统是否可用。

验收标准：

- 执行文档规定的启动命令后，核心容器能够完成启动
- 默认站点能够访问登录页
- 用户可以通过约定的管理员凭据登录
- 文档明确说明该模式适合体验，不作为生产部署方案

### US-002 选择生产部署拓扑

作为部署人员，我希望按数据库、Redis、入口和 HTTPS 需求选择 override，以便在不修改核心 Compose 的情况下部署。

验收标准：

- 文档列出直连、HTTP 代理、HTTPS、外部依赖和多 bench 的组合方式
- 每种组合明确必填环境变量、端口、网络和持久化卷
- 生成的最终 Compose 配置能够被检查和审阅
- 未选择的可选服务不会被隐式启动

### US-003 交付自定义 app

作为应用团队，我希望在构建阶段注入自定义 app，以便镜像可复制、可扩容和可回滚。

验收标准：

- 构建参数或 secret 能传递 app 清单、仓库和版本
- 构建成功后，容器内可发现并加载目标 app
- 新容器不依赖手工执行 `bench get-app`
- 镜像 tag 能对应 Frappe、ERPNext 和自定义 app 的版本组合

### US-004 本地开发与调试

作为开发人员，我希望使用 Devcontainer 启动 bench、数据库和 Redis，并能调试 Python、worker、scheduler 和 Socket.IO。

验收标准：

- Devcontainer 能启动开发依赖服务
- 初始化脚本能创建 bench、站点并安装示例 apps
- VS Code 配置能提供后端和后台进程的调试入口
- 开发环境的端口、数据卷和生产环境边界在文档中明确

### US-005 发布前自动验证

作为维护者，我希望在镜像发布前运行集成测试，以便降低破坏核心运行链路的风险。

验收标准：

- CI 能构建或拉取待测镜像并启动测试 Compose
- 测试覆盖 HTTP、数据库、Redis、assets、文件安全、HTTPS 和备份等关键路径
- 测试失败时不会继续发布对应镜像
- 至少支持项目声明的主要架构构建验证

## 9.2 模块级验收标准

| 模块 | 验收重点 |
| --- | --- |
| 核心编排 | backend、frontend、websocket、worker、scheduler 能在 configurator 完成后启动 |
| 数据库与 Redis | 配置可通过内置服务、外部地址或 secret 注入，连接失败有明确日志 |
| 镜像 | 生产、custom、layered、bench 镜像职责清晰，应用和 assets 在构建期确定 |
| Web 入口 | HTTP 请求、WebSocket、静态资源、上传大小和安全头符合配置 |
| 站点生命周期 | 能创建站点、执行迁移、安装 app，并说明数据卷边界 |
| 代理与证书 | 选定的代理能转发站点请求，HTTPS 模式能加载证书或完成 ACME 配置 |
| 备份 | 备份命令可以被定时触发，备份结果能写入声明的目标存储并可检查 |
| 开发容器 | 开发者可以启动依赖、初始化 bench 并进入调试流程 |
| CI/CD | lint、测试、构建、发布和文档发布有可追踪的工作流结果 |
| 文档 | 使用者能从入口文档定位到对应拓扑、变量、命令和排障说明 |

## 10. 当前风险

- 文档中少量旧路径和旧术语需要持续修正
- 本地开发产物容易污染工作区
- 部分 override 仍缺少单独说明
- 新增能力会同时影响镜像、Compose、测试和文档，改动面较大

## 10.1 明确不在本项目范围内

- Frappe、ERPNext 或其他 app 的业务功能设计
- 用户、角色、权限、财务、库存等业务数据模型
- 云厂商 Kubernetes/托管数据库的完整运维控制台
- 完整的日志平台、监控平台、告警平台和工单系统
- 自动替用户决定生产拓扑、域名、证书、容量和备份保留策略
- 替代 Docker、Compose、MariaDB、PostgreSQL、Redis 或反向代理本身

这些能力可以由下游平台或运维体系补充，但不应作为本仓库的默认产品承诺。

## 11. 迭代建议

1. 补全 override 说明矩阵
2. 统一文档中的路径和术语
3. 清理未引用测试脚本
4. 增强本地开发与生产部署的边界提示
5. 给多 bench、自定义域名、备份 cron 单独补文档

## 11.1 建议迭代顺序

### 近期：完善当前能力的可用性

- 修正文档中的旧路径、旧文件名和 Werkzeug/Gunicorn 术语不一致
- 为每个 override 增加前置条件、环境变量、典型组合和回滚说明
- 将快速体验、开发和生产部署的入口明确分开
- 为迁移、备份、HTTPS 和多 bench 增加最小验收清单

### 中期：提高交付一致性

- 为常见部署拓扑提供可复制的示例和生成后的 Compose 校验
- 增加镜像版本、app 版本和数据库迁移状态的可追踪信息
- 增强备份恢复演练文档和失败场景测试
- 补充多架构构建、外部依赖和自定义域名的 CI 覆盖

### 长期：降低平台维护成本

- 形成稳定版、开发版和下游 app 镜像的版本兼容矩阵
- 建立文档、Compose、镜像和测试之间的需求追踪关系
- 评估是否需要为常见生产场景提供更高层的部署模板或配置生成工具

## 12. 需求追踪与变更规则

每次涉及以下任一项的变更，都应同步评估镜像、Compose、测试和文档：

- Frappe/ERPNext、Python、Node、MariaDB、PostgreSQL 或 Redis 版本
- 站点初始化、迁移、备份和 assets 处理逻辑
- Nginx、Traefik、nginx-proxy、Caddy 或 HTTPS 配置
- 自定义 app 的构建参数、secret 和依赖安装方式
- CI 的镜像 tag、架构矩阵、发布仓库和下游工作流接口

建议以 `FR-*` 功能需求和 `US-*` 用户故事作为 PR 描述中的关联编号。涉及 P0 能力的改动，至少应补充或更新一条自动化测试；仅文档、示例或 P1 拓扑改动，也应更新对应使用说明和验收步骤。
