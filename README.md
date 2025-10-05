# Civitai模型更新检查器

这是一个用于监控Civitai网站上模型更新的Python脚本，可以帮助您跟踪并及时了解您关注的模型的最新版本。

## 🚀 功能特性

- ✅ 监控多个Civitai模型的更新
- ✅ 自动检测新版本发布
- ✅ 支持定时检查（守护进程模式）
- ✅ 保存历史版本记录
- ✅ 支持模型别名管理
- ✅ 可选的API key支持（用于访问需要认证的功能）
- 🌐 **支持代理服务器**（适用于企业网络或网络受限环境）
- 🔍 内置诊断工具（用于排查常见问题）

## 📦 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 添加要监控的模型

```bash
python civitai_checker.py --add https://civitai.com/models/12345 --alias "我的模型"
```

### 3. 查看已添加的模型

```bash
python civitai_checker.py --list
```

### 4. 检查更新

```bash
python civitai_checker.py --check
```

### 5. 设置定时检查

#### 方法1: 使用守护进程模式
```bash
python civitai_checker.py --daemon
```

#### 方法2: 使用Windows任务计划（推荐）
1. 运行 `python setup_schedule.py`
2. 按照提示创建定时任务

## 📖 详细使用说明

### 基本命令

```bash
# 添加模型监控
python civitai_checker.py --add <URL> [--alias <别名>]

# 移除模型监控
python civitai_checker.py --remove <ID或别名>

# 列出所有监控的模型
python civitai_checker.py --list

# 手动检查更新
python civitai_checker.py --check

# 守护进程模式（持续运行）
python civitai_checker.py --daemon
```

### API Key设置（可选）

大部分功能不需要API key，只有在以下情况才需要：
- 访问需要登录的私有模型
- 下载某些需要认证的模型文件
- 访问个人收藏列表

```bash
# 设置API key
python civitai_checker.py --set-api-key "your_api_key_here"

# 清除API key
python civitai_checker.py --set-api-key ""
```

**获取API key**: 访问 [Civitai用户设置](https://civitai.com/user/account)

### 代理服务器设置

适用于企业网络或需要代理访问的环境：

```bash
# 基本代理设置
python civitai_checker.py --proxy-http "http://proxy.example.com:8080"
python civitai_checker.py --proxy-https "https://proxy.example.com:8080"

# 带认证的代理
python civitai_checker.py --proxy-username "user" --proxy-password "pass"

# 代理管理
python civitai_checker.py --show-proxy      # 查看代理配置
python civitai_checker.py --enable-proxy    # 启用代理
python civitai_checker.py --disable-proxy   # 禁用代理
```

## ⚙️ 配置文件

程序会自动创建 `config.json` 配置文件：

```json
{
  "models": [],
  "check_interval_hours": 24,
  "api_key": "",
  "proxy": {
    "enabled": false,
    "http": "",
    "https": "",
    "username": "",
    "password": ""
  },
  "notification": {
    "enabled": false,
    "email": ""
  }
}
```

## 🔧 故障排除

### 网络连接问题

如果遇到网络连接错误：

1. **运行诊断工具**
   ```bash
   python diagnose.py
   ```
   诊断工具会检查：
   - Python版本兼容性
   - 依赖包安装情况
   - 文件完整性
   - 配置文件格式
   - 网络连接状态

2. **企业网络环境**
   - 配置代理服务器（见上方代理设置）
   - 检查防火墙设置
   - 确保proxy设置中enabled已设为true

3. **API访问问题**
   - 验证API key有效性（可在Civitai网站个人设置中重新生成）
   - 检查模型是否为私有模型（某些模型需要登录才能访问）

### 常见错误解决

- **模型不存在 (HTTP 404)**: 检查模型URL是否正确
- **请求超时**: 检查网络连接或配置代理
- **代理认证失败 (HTTP 407)**: 检查代理用户名和密码
- **配置文件错误**: 删除config.json让程序重新创建

### 代理配置问题

1. **测试代理连接**
   ```bash
   python test_proxy.py
   ```

2. **常见代理格式**
   - `http://proxy.example.com:8080`
   - `https://proxy.example.com:8080`

3. **企业域认证**
   ```bash
   python civitai_checker.py --proxy-username "DOMAIN\\username"
   ```

## 📁 项目文件说明

- `civitai_checker.py` - 主程序，用于检查模型更新
- `config.json` - 配置文件（自动生成），存储监控的模型列表和程序设置
- `model_history.json` - 历史记录文件（自动生成），记录模型的最近检查和更新信息
- `requirements.txt` - Python依赖包列表，仅依赖requests库
- `setup_schedule.py` - Windows定时任务设置助手，帮助创建自动检查任务
- `diagnose.py` - 系统诊断工具，用于排查常见问题

## 🌟 使用示例

### 监控多个模型
```bash
# 添加几个热门模型
python civitai_checker.py --add https://civitai.com/models/4384 --alias "DreamShaper"
python civitai_checker.py --add https://civitai.com/models/4201 --alias "Realistic Vision"
python civitai_checker.py --add https://civitai.com/models/6424 --alias "ChilloutMix"

# 查看列表
python civitai_checker.py --list

# 检查更新
python civitai_checker.py --check
```

### 设置自动监控
```bash
# 启动24小时定时检查
python civitai_checker.py --daemon

# 或者设置Windows定时任务
python setup_schedule.py
```

### 使用代理服务器
```bash
# 设置HTTP代理
python civitai_checker.py --proxy-http "http://127.0.0.1:10808"

# 设置HTTPS代理
python civitai_checker.py --proxy-https "http://127.0.0.1:10808"

# 启用代理
python civitai_checker.py --enable-proxy

# 检查代理设置
python civitai_checker.py --show-proxy
```

### 诊断问题
```bash
# 运行诊断工具
python diagnose.py
```

## 🔒 安全注意事项

- 📁 配置文件包含敏感信息（API key、代理密码），请妥善保管
- 🔐 不要在公共环境中暴露配置文件
- 🌐 使用可信的代理服务器
- 🔄 定期更新依赖包：`pip install --upgrade requests`

## 📝 更新日志

### v2.1.0 (2025-09-02)
- 🔄 优化代理服务器配置处理
- 🛠️ 完善诊断工具功能
- 📊 改进历史记录格式
- 🐛 修复了多处网络连接问题

### v2.0.0
- ➕ 新增代理服务器支持
- 🔧 改进网络请求稳定性
- 📖 完善错误处理和用户提示
- 🛠️ 添加诊断和测试工具

### v1.0.0
- 🎉 基础模型监控功能
- ⏰ 定时检查和守护进程
- 🔑 API key支持
- 📱 Windows批处理文件

## 🤝 贡献

欢迎提交问题和改进建议！

## 📄 许可证

MIT License

---

**支持的模型URL格式**:
- `https://civitai.com/models/12345`
- `https://civitai.com/models/12345/model-name`

**注意事项**:
- 首次检查时会记录当前版本，不会报告更新
- 建议每天检查1-2次，避免频繁请求
- 需要网络连接才能正常工作
