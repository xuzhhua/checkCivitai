# Civitai Checker 远程部署与 Docker 化设计

## 背景

当前项目是单文件脚本配合本地 `config.json` 和 `model_history.json` 运行，适合本机直接执行，但不适合稳定部署到局域网里的远端 Windows Docker Desktop 主机。

目标环境是一台 IP 为 `192.168.173.22` 的 Windows 主机，已经安装 Docker Desktop，并计划通过 SSH 从本地进行远程发布。参考实现为同工作区下的 `rss2Mail` 项目，其发布方式是：本地构建镜像并导出，使用 SSH/SCP 上传到远端，再在远端执行 `docker load` 和 `docker compose up`。

本次改造同时需要满足以下新增要求：

- 支持 `https://civitai.red`
- 保持代理可用，默认仍考虑 `127.0.0.1:10808`
- Docker 化后仍然方便添加和删除监控模型

## 目标

- 将项目封装为可在 Docker 中长期运行的守护进程
- 保留现有命令行能力，包括添加、删除、列出和手动检查模型
- 支持通过 SSH 将项目一键发布到远端 Windows Docker Desktop 主机
- 将运行时配置和历史记录从镜像中分离，避免镜像升级覆盖数据
- 同时支持 `civitai.com` 和 `civitai.red` 的模型 URL 与 API 访问
- 为 Docker 部署后的模型增删提供简单入口，避免手工编辑 JSON 文件

## 非目标

- 不新增 Web UI
- 不新增长期运行的 REST 管理服务
- 不将项目拆分为多服务架构
- 不重写为数据库存储，继续使用 JSON 文件

## 总体方案

### 运行方式

容器默认以守护模式运行，等价于当前脚本的 `--daemon` 行为。容器启动命令固定为执行检查器主程序的守护模式，以便远端主机只需保证 Docker Desktop 运行即可持续监控。

### 数据持久化

镜像中不内置敏感配置和运行历史。通过 Docker volume 或宿主机目录挂载以下文件到容器内：

- `config.json`
- `model_history.json`

容器内部程序需要支持从环境变量或参数接收配置目录，从而把默认读写位置从当前工作目录迁移到可挂载的数据目录。

### 远程发布方式

沿用 `rss2Mail` 的经过验证的方案：

1. 本地 `docker compose build`
2. 本地 `docker save`
3. 通过 `scp` 上传项目压缩包和镜像 tar 到远端 Windows 主机
4. 通过 `ssh` 在远端执行 PowerShell，完成解压、`docker load`、`docker compose up --no-build`

这样可以避免在远端 Windows SSH 会话里直接构建镜像，降低 Docker Desktop 凭据和会话兼容问题。

## 应用层改造

### 站点来源建模

当前实现把 API 基址固定为 `https://civitai.com/api/v1`，并且 URL 解析只接受 `civitai.com`。改造后需要把“模型来源站点”视为模型元数据的一部分。

每个模型项新增可推导或显式记录的字段：

- `site`: 取值为 `civitai.com` 或 `civitai.red`

行为规则如下：

- 新增模型时，从传入 URL 自动解析站点和模型 ID
- 已存在的旧配置若没有 `site`，默认视为 `civitai.com`
- 检查更新时，按模型对应的 `site` 选择 API 基址
- 生成模型详情链接时，优先使用模型自身记录的 URL

### URL 与 API 支持

需要支持以下 URL 形态：

- `https://civitai.com/models/<id>`
- `https://civitai.com/models/<id>/<slug>`
- `https://civitai.red/models/<id>`
- `https://civitai.red/models/<id>/<slug>`

API 基址规则：

- `civitai.com` -> `https://civitai.com/api/v1`
- `civitai.red` -> `https://civitai.red/api/v1`

### 配置与路径抽象

当前程序把 `config.json` 和 `model_history.json` 固定在脚本当前目录。改造后增加一个统一的数据目录概念，例如：

- 默认仍兼容当前目录
- 当设置环境变量时，优先从指定数据目录读取和写入

建议引入如下环境变量：

- `CIVITAI_CHECKER_DATA_DIR`

当该变量存在时：

- 配置文件路径为 `<data_dir>/config.json`
- 历史文件路径为 `<data_dir>/model_history.json`

这样既兼容本地旧用法，也便于容器挂载。

### 模型管理入口

不新增独立服务，继续复用现有 CLI 参数。

Docker 化后提供两层操作方式：

1. 容器默认长期运行守护模式
2. 提供本地 PowerShell 管理脚本，通过 SSH 在远端调用一次性容器命令或 `docker compose exec` 完成：
   - 添加模型
   - 删除模型
   - 列出模型
   - 立即检查

管理脚本的目标是让常见操作保持类似下面的体验：

- 远端添加模型
- 远端删除模型
- 查看当前列表

该脚本不负责修改业务逻辑，只负责把参数透传到远端已部署容器。

## Docker 设计

### Dockerfile

采用 Python slim 基础镜像，安装 `requirements.txt`，复制项目源码。默认入口执行守护模式。

镜像内需要设置：

- `PYTHONDONTWRITEBYTECODE=1`
- `PYTHONUNBUFFERED=1`
- `TZ=Asia/Shanghai`

### docker-compose.yml

Compose 中定义单服务，例如 `civitai-checker`。

关键点：

- `restart: unless-stopped`
- 挂载 `./data` 到容器的数据目录
- 通过环境变量指定 `CIVITAI_CHECKER_DATA_DIR`
- 默认命令为守护模式

远端部署目录中的 `data` 文件夹保存真实配置与历史记录。

## 代理策略

### 构建阶段代理

本地构建镜像时，继续使用 `127.0.0.1:10808` 作为本机代理。部署脚本会在当前 PowerShell 进程内临时设置：

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `http_proxy`
- `https_proxy`
- `NO_PROXY`

默认值保持为 `127.0.0.1:10808`，与参考项目一致。

### 运行阶段代理

容器内如果仍配置 `127.0.0.1:10808`，访问到的是容器自身，而不是远端 Windows 宿主机。因此远端 Docker 运行时默认代理值应切换为：

- `http://host.docker.internal:10808`

配置处理规则：

- 部署模板或示例配置中，远端 Docker 场景默认给出 `host.docker.internal:10808`
- 如果用户明确知道远端代理部署在别的地址，则允许保持自定义
- 旧本地运行方式仍可继续使用 `127.0.0.1:10808`

## 远程管理脚本

### 发布脚本

新增 `deploy.ps1`，结构和 `rss2Mail` 保持一致：

- 接收远端用户、主机、端口、目标目录、私钥路径、代理参数
- 本地构建 compose 镜像
- 导出镜像 tar
- 打包项目文件
- 上传到远端
- 远端执行 PowerShell 完成部署

默认参数：

- `RemoteHost = 192.168.173.22`
- `RemotePort = 22`
- 默认本地构建代理 `127.0.0.1:10808`

### 管理脚本

新增一个单独的管理脚本，例如 `manage_remote.ps1`，用于对远端已部署实例执行常见操作。职责包括：

- `add`
- `remove`
- `list`
- `check`

该脚本通过 SSH 在远端部署目录中执行 `docker compose exec` 或短生命周期 `docker compose run --rm`。优先选择不会干扰守护容器的方式。

## 配置兼容性

### 旧配置升级

现有 `config.json` 结构保持总体兼容，只在模型项中允许出现可选 `site` 字段。

若读取到旧模型项：

- 没有 `site`
- URL 是 `civitai.com`

则运行时自动推断 `site = civitai.com`，无需强制迁移已有配置。

### 示例配置

仓库中应新增适合 Docker 部署的示例配置，避免把真实邮箱密码、API key 等敏感信息写入版本库。

## 测试策略

采用测试优先方式，先补失败测试，再补实现。

最少覆盖以下行为：

- 从 `civitai.com` URL 中提取站点与模型 ID
- 从 `civitai.red` URL 中提取站点与模型 ID
- 旧配置中未声明 `site` 时能兼容读取
- 根据 `site` 选择正确 API 基址
- 数据目录环境变量生效后，配置文件和历史文件读写路径正确

如果当前仓库没有测试基础设施，需要先补一个最小的 Python 单元测试入口，再围绕上述行为写测试。

## 文档更新

README 需要新增以下内容：

- Docker 本地运行方法
- 远程部署方法
- 远端 Docker 场景下的代理说明
- `civitai.red` 支持说明
- Docker 部署后如何添加和删除模型

## 风险与处理

### 风险 1：容器内代理地址不可达

处理：在 README 和示例配置中明确区分“本机运行”与“Docker 运行”的代理地址差异。

### 风险 2：远端 Windows 下 compose exec 行为与终端编码问题

处理：管理脚本尽量使用简单参数传递，并保持 PowerShell 编码和 SSH 调用方式与参考项目一致。

### 风险 3：旧配置中包含敏感信息并被误上传

处理：默认不上传真实配置文件，只在显式参数下允许覆盖远端配置，并提供示例配置模板。

## 实施顺序

1. 补测试基础设施与关键失败测试
2. 改造站点解析、API 基址选择和数据目录抽象
3. 补 Dockerfile、compose 和示例配置
4. 补远程发布脚本
5. 补远端管理脚本
6. 更新 README
7. 做本地聚焦验证

## 结论

本次改造保持项目单进程、单容器、JSON 配置的简单形态，不引入额外服务。部署链路完全对齐已验证的 `rss2Mail` 方案，新增的复杂度主要集中在三个点：

- 站点来源建模与 `civitai.red` 支持
- 数据目录抽象以适配容器挂载
- 远端管理脚本以保持添加和删除模型的便利性

这套方案的目标不是做成平台化服务，而是在尽量少改动现有脚本结构的前提下，把它提升为可稳定远程部署和维护的 Docker 应用。