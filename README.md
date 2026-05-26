# Civitai模型更新检查器

一个用于监控 Civitai 模型更新的 Python 工具，支持直接本机运行，也支持打包成 Docker 容器部署到局域网里的远端 Windows Docker Desktop 主机。

## 功能特性

- 支持 `https://civitai.com` 和 `https://civitai.red`
- 监控多个模型并记录最近一次版本状态
- 支持别名、按 URL 精确删除、手动检查和守护进程模式
- 支持 API key、SMTP 邮件通知和代理配置
- 支持通过 `CIVITAI_CHECKER_DATA_DIR` 切换配置与历史记录目录
- 提供 Docker 运行面、远程部署脚本和远端模型管理脚本
- 提供诊断工具和基础单元测试

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 添加模型

```bash
python civitai_checker.py --add https://civitai.com/models/4384 --alias "DreamShaper"
python civitai_checker.py --add https://civitai.red/models/1522819 --alias "Red Mirror"
```

### 3. 查看和检查

```bash
python civitai_checker.py --list
python civitai_checker.py --check
```

### 4. 持续运行

```bash
python civitai_checker.py --daemon
```

如果你仍然想走宿主机计划任务，也可以继续使用：

```bash
python setup_schedule.py
```

## 配置文件

默认情况下，程序会在当前目录读写：

- `config.json`
- `model_history.json`

如果设置了环境变量 `CIVITAI_CHECKER_DATA_DIR`，则会改为从该目录读取和写入这两个文件。这一机制主要用于 Docker 挂载数据目录。

仓库提供了一个不含真实凭据的模板：

- `config.example.json`

### 代理说明

如果你直接在宿主机运行脚本，并且代理就在宿主机本机，通常可以继续使用：

- `http://127.0.0.1:10808`

如果你在 Docker 容器里运行，容器内的 `127.0.0.1` 指向容器自身，不再是宿主机。远端 Windows Docker Desktop 场景建议改为：

- `http://host.docker.internal:10808`

## 常用命令

```bash
# 添加模型
python civitai_checker.py --add <URL> [--alias <别名>]

# 移除模型
python civitai_checker.py --remove <ID|别名|完整URL>

# 列出模型
python civitai_checker.py --list

# 手动检查
python civitai_checker.py --check

# 守护进程模式
python civitai_checker.py --daemon

# 设置 API key
python civitai_checker.py --set-api-key "your_api_key"

# 代理设置
python civitai_checker.py --proxy-http "http://127.0.0.1:10808"
python civitai_checker.py --proxy-https "http://127.0.0.1:10808"
python civitai_checker.py --enable-proxy
python civitai_checker.py --show-proxy
```

## Docker 本地运行

### 1. 准备数据目录

创建 `data` 目录，并把模板配置复制进去：

```bash
mkdir data
cp config.example.json data/config.json
```

如果你已经有现成的本地配置，也可以直接复制当前 `config.json` 到 `data/config.json`。

### 2. 构建并启动

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

停止：

```bash
docker compose down
```

Compose 会把 `./data` 挂载到容器内的 `/app/data`，容器默认以守护模式运行。

## 远程部署到 Windows Docker Desktop

当前仓库已提供 `deploy.ps1`，默认目标就是：

- 主机：`192.168.173.22`
- 端口：`22`
- 远端目录：`D:\ProgramFiles\checkCivitai`

### 前置条件

- 本机可用 `ssh`、`scp`、`docker`
- 远端 Windows 已启用 OpenSSH Server
- 远端 Docker Desktop 已正常启动
- 远端已经存在 `data/config.json`，或你准备在发布时用 `-UploadConfig` 上传本机配置

### 常用发布方式

首次把本机配置一并上传：

```powershell
.\deploy.ps1 -RemoteUser username -UploadConfig
```

后续只更新镜像和代码，不覆盖远端配置：

```powershell
.\deploy.ps1 -RemoteUser username
```

指定私钥：

```powershell
.\deploy.ps1 -RemoteUser username -IdentityFile C:\Users\you\.ssh\checkcivitai_ed25519
```

先看将执行什么：

```powershell
.\deploy.ps1 -RemoteUser username -DryRun
```

### 构建代理

部署脚本默认会在本机构建镜像时设置：

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `http_proxy`
- `https_proxy`
- `NO_PROXY`

默认代理地址是：

- `127.0.0.1:10808`

如果要改，显式传入：

```powershell
.\deploy.ps1 -RemoteUser username -ProxyUrl 127.0.0.1:10808
```

## 远端模型管理

远端部署后，不需要手工登录容器编辑 JSON。仓库提供了 `manage_remote.ps1`。

### 添加模型

```powershell
.\manage_remote.ps1 -RemoteUser username -Action add -ModelUrl https://civitai.red/models/1522819 -Alias RedMirror
```

### 删除模型

建议优先用别名或完整 URL 删除：

```powershell
.\manage_remote.ps1 -RemoteUser username -Action remove -ModelKey RedMirror
.\manage_remote.ps1 -RemoteUser username -Action remove -ModelKey https://civitai.red/models/1522819
```

### 查看列表

```powershell
.\manage_remote.ps1 -RemoteUser username -Action list
```

### 立即检查

```powershell
.\manage_remote.ps1 -RemoteUser username -Action check
```

## 诊断与验证

### 运行诊断工具

```bash
python diagnose.py
```

### 运行单元测试

```bash
python -m unittest tests.test_civitai_checker
```

## 常见问题

### 1. Docker 容器里代理不生效

大概率是把 `127.0.0.1:10808` 原样带进了容器。容器里应该优先使用：

- `http://host.docker.internal:10808`

### 2. 远端部署脚本提示缺少 `data/config.json`

这是为了避免容器带着空配置启动。解决方式二选一：

- 先在远端 `D:\ProgramFiles\checkCivitai\data\config.json` 准备配置
- 首次发布时使用 `-UploadConfig`

### 3. 模型 URL 解析失败

当前支持：

- `https://civitai.com/models/<id>`
- `https://civitai.com/models/<id>/<slug>`
- `https://civitai.red/models/<id>`
- `https://civitai.red/models/<id>/<slug>`

### 4. 首次检查没有提示更新

这是正常行为。首次检查只会记录当前版本作为基线，不会把现有版本当成“新更新”。

## 项目文件

- `civitai_checker.py`：主程序
- `diagnose.py`：诊断工具
- `setup_schedule.py`：宿主机计划任务助手
- `Dockerfile`：容器镜像定义
- `docker-compose.yml`：单容器守护运行配置
- `deploy.ps1`：本地构建并通过 SSH 发布到远端 Windows Docker Desktop
- `manage_remote.ps1`：远端模型管理入口
- `config.example.json`：配置模板
- `tests/test_civitai_checker.py`：基础单元测试

## 安全提醒

- 不要把真实 `config.json`、邮箱密码、API key 提交到版本库
- 如果你已经在仓库里放过真实凭据，建议尽快轮换
- 只在显式需要时使用 `deploy.ps1 -UploadConfig`

## 许可证

MIT License
