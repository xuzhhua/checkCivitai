#!/usr/bin/env python3
"""
Civitai Model Update Checker
检查Civitai模型更新的脚本
"""

import requests
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse
import smtplib
from urllib.parse import urlparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header


class CivitaiChecker:
    API_BASE_URLS = {
        "civitai.com": "https://civitai.com/api/v1",
        "civitai.red": "https://civitai.red/api/v1",
    }

    def __init__(self, config_file: str = "config.json"):
        self.data_dir = os.environ.get("CIVITAI_CHECKER_DATA_DIR", "")
        self.config_file = self._resolve_data_path(config_file)
        self.history_file = self._resolve_data_path("model_history.json")
        self.base_url = self.get_api_base_url()
        self.config = self.load_config()
        self.api_key = self.config.get("api_key", "")

    def _resolve_data_path(self, file_name: str) -> str:
        """根据数据目录环境变量解析配置和历史文件路径"""
        if os.path.isabs(file_name) or os.path.dirname(file_name):
            return file_name

        if self.data_dir:
            return os.path.join(self.data_dir, file_name)

        return file_name

    def _ensure_parent_dir(self, file_path: str):
        """确保目标文件的父目录存在"""
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    def normalize_model_site(self, site: str = "") -> str:
        """规范化模型站点名称"""
        normalized_site = (site or "").strip().lower()
        if normalized_site.startswith("www."):
            normalized_site = normalized_site[4:]

        if normalized_site in self.API_BASE_URLS:
            return normalized_site

        return "civitai.com"

    def extract_model_reference(self, url: str) -> Optional[Dict[str, str]]:
        """从URL中提取模型站点和模型ID"""
        try:
            parsed_url = urlparse(url)
            raw_site = (parsed_url.netloc or "").strip().lower()
            if raw_site.startswith("www."):
                raw_site = raw_site[4:]

            if raw_site not in self.API_BASE_URLS:
                print("URL站点不受支持，仅支持 civitai.com 和 civitai.red")
                return None

            site = raw_site
            path_parts = [part for part in parsed_url.path.split("/") if part]

            if len(path_parts) < 2 or path_parts[0] != "models":
                print("URL格式不正确，应该包含 '/models/<id>'")
                return None

            model_id = path_parts[1]
            if not model_id.isdigit():
                print(f"无效的模型ID: {model_id}")
                return None

            return {"site": site, "model_id": model_id}
        except (AttributeError, ValueError) as e:
            print(f"URL解析错误: {e}")
            return None

    def get_model_site(self, model: Optional[Dict] = None) -> str:
        """获取模型所属站点，兼容旧配置"""
        if not model:
            return "civitai.com"

        if model.get("site"):
            return self.normalize_model_site(model.get("site", ""))

        model_url = model.get("url", "")
        reference = self.extract_model_reference(model_url) if model_url else None
        if reference:
            return reference["site"]

        return "civitai.com"

    def get_api_base_url(self, model: Optional[Dict] = None) -> str:
        """根据模型来源站点选择API基址"""
        return self.API_BASE_URLS[self.get_model_site(model)]
        
    def _get_headers(self) -> Dict:
        """获取请求头，如果有API key则添加认证"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _get_params(self, params: Dict = None) -> Dict:
        """获取请求参数，如果有API key则添加token参数"""
        if params is None:
            params = {}
        if self.api_key:
            params["token"] = self.api_key
        return params
    
    def _get_proxies(self) -> Dict:
        """获取代理配置"""
        proxy_config = self.config.get("proxy", {})
        if not proxy_config.get("enabled", False):
            return {}
        
        proxies = {}
        http_proxy = proxy_config.get("http", "")
        https_proxy = proxy_config.get("https", "")
        username = proxy_config.get("username", "")
        password = proxy_config.get("password", "")
        
        # 如果需要认证，构建带认证的代理URL
        if username and password:
            if http_proxy:
                # 从URL中提取协议和地址
                if "://" in http_proxy:
                    protocol, address = http_proxy.split("://", 1)
                    proxies["http"] = f"{protocol}://{username}:{password}@{address}"
                else:
                    proxies["http"] = f"http://{username}:{password}@{http_proxy}"
            
            if https_proxy:
                if "://" in https_proxy:
                    protocol, address = https_proxy.split("://", 1)
                    proxies["https"] = f"{protocol}://{username}:{password}@{address}"
                else:
                    proxies["https"] = f"https://{username}:{password}@{https_proxy}"
        else:
            # 不需要认证的代理
            if http_proxy:
                proxies["http"] = http_proxy
            if https_proxy:
                proxies["https"] = https_proxy
        
        return proxies
        
    def load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 创建默认配置
            default_config = {
                "models": [],
                "check_interval_hours": 24,
                "api_key": "",  # 可选的API key，用于访问需要认证的功能
                "proxy": {
                    "enabled": False,
                    "http": "",     # HTTP代理地址，如: "http://proxy.example.com:8080"
                    "https": "",    # HTTPS代理地址，如: "https://proxy.example.com:8080"
                    "username": "", # 代理用户名（如果需要认证）
                    "password": ""  # 代理密码（如果需要认证）
                },
                "notification": {
                    "enabled": False,
                    "email": {
                        "smtp_server": "smtp.gmail.com",  # SMTP服务器地址
                        "smtp_port": 587,                  # SMTP端口
                        "use_tls": True,                   # 是否使用TLS
                        "username": "",                    # 发件人邮箱
                        "password": "",                    # 邮箱密码或应用专用密码
                        "from_addr": "",                   # 发件人地址（通常与username相同）
                        "to_addr": ""                      # 收件人地址
                    }
                }
            }
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Dict):
        """保存配置文件"""
        self._ensure_parent_dir(self.config_file)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def load_history(self) -> Dict:
        """加载历史记录"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_history(self, history: Dict):
        """保存历史记录"""
        self._ensure_parent_dir(self.history_file)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    
    def extract_model_id(self, url: str) -> Optional[str]:
        """从URL中提取模型ID"""
        reference = self.extract_model_reference(url)
        if not reference:
            return None

        return reference["model_id"]
    
    def _make_request(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """统一的网络请求方法，包含重试机制和代理支持"""
        headers = self._get_headers()
        params = self._get_params()
        proxies = self._get_proxies()
        
        # 如果启用了代理，显示代理信息（隐藏认证信息）
        if proxies:
            proxy_info = {}
            for key, proxy_url in proxies.items():
                if "@" in proxy_url:
                    # 隐藏认证信息
                    parts = proxy_url.split("@")
                    proxy_info[key] = f"***@{parts[-1]}"
                else:
                    proxy_info[key] = proxy_url
            print(f"  使用代理: {proxy_info}")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, params=params, 
                                      proxies=proxies, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                print(f"  请求超时，正在重试... ({attempt + 1}/{max_retries})")
            except requests.exceptions.ConnectionError as e:
                if proxies:
                    print(f"  代理连接错误，正在重试... ({attempt + 1}/{max_retries})")
                    print(f"  错误详情: {str(e)[:100]}")
                else:
                    print(f"  连接错误，正在重试... ({attempt + 1}/{max_retries})")
            except requests.exceptions.ProxyError:
                print(f"  代理服务器错误，正在重试... ({attempt + 1}/{max_retries})")
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response is not None:
                    response = e.response
                    if response.status_code == 404:
                        print(f"  模型不存在或已被删除 (HTTP 404)")
                        return None
                    elif response.status_code == 407:
                        print(f"  代理认证失败 (HTTP 407) - 请检查代理用户名和密码")
                        return None
                    elif response.status_code == 429:
                        print(f"  请求过于频繁，等待更长时间后重试... ({attempt + 1}/{max_retries})")
                        time.sleep(5)  # 429错误等待更长时间
                    else:
                        print(f"  HTTP错误: {e} ({attempt + 1}/{max_retries})")
                else:
                    print(f"  HTTP错误: {e} ({attempt + 1}/{max_retries})")
            except Exception as e:
                print(f"  请求失败: {e} ({attempt + 1}/{max_retries})")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
        
        return None
    
    def get_model_info(self, model_id: str, site: str = "civitai.com") -> Optional[Dict]:
        """获取模型信息"""
        api_base_url = self.API_BASE_URLS[self.normalize_model_site(site)]
        url = f"{api_base_url}/models/{model_id}"
        result = self._make_request(url)
        if result is None:
            print(f"获取模型 {model_id} 信息失败")
        return result
    
    def get_model_versions(self, model_id: str, site: str = "civitai.com") -> List[Dict]:
        """获取模型版本列表"""
        # 先尝试从模型详情中获取版本信息
        api_base_url = self.API_BASE_URLS[self.normalize_model_site(site)]
        model_info = self.get_model_info(model_id, site=site)
        if model_info and "modelVersions" in model_info:
            return model_info["modelVersions"]
        
        # 如果没有版本信息，尝试直接版本API
        url = f"{api_base_url}/models/{model_id}/versions"
        result = self._make_request(url)
        
        if result:
            return result.get("items", [])
        elif model_info:
            # 如果版本API失败，从模型信息中提取
            return model_info.get("modelVersions", [])
        else:
            print(f"无法获取模型 {model_id} 的版本信息")
            return []
    
    def add_model(self, model_url: str, alias: str = ""):
        """添加要监控的模型"""
        reference = self.extract_model_reference(model_url)
        if not reference:
            print("无效的模型URL")
            return False

        model_id = reference["model_id"]
        site = reference["site"]
        
        # 获取模型信息验证
        model_info = self.get_model_info(model_id, site=site)
        if not model_info:
            print("无法获取模型信息，请检查URL是否正确")
            return False
        
        # 添加到配置
        model_entry = {
            "id": model_id,
            "site": site,
            "url": model_url,
            "name": model_info.get("name", "Unknown"),
            "alias": alias or model_info.get("name", "Unknown"),
            "added_date": datetime.now().isoformat()
        }
        
        # 检查是否已存在
        for model in self.config["models"]:
            if model["id"] == model_id and self.get_model_site(model) == site:
                print(f"模型 {model['name']} 已在监控列表中")
                return False
        
        self.config["models"].append(model_entry)
        self.save_config(self.config)
        
        print(f"已添加模型: {model_entry['name']} (ID: {model_id})")
        return True
    
    def set_api_key(self, api_key: str):
        """设置API key"""
        self.config["api_key"] = api_key
        self.api_key = api_key
        self.save_config(self.config)
        if api_key:
            print("✅ API key已设置")
        else:
            print("❌ API key已清除")
    
    def set_proxy(self, http_proxy: str = None, https_proxy: str = None, 
                  username: str = None, password: str = None, enabled: bool = None):
        """设置代理服务器"""
        if "proxy" not in self.config:
            self.config["proxy"] = {
                "enabled": False,
                "http": "",
                "https": "",
                "username": "",
                "password": ""
            }
        
        proxy_config = self.config["proxy"]
        
        if enabled is not None:
            proxy_config["enabled"] = enabled
        
        if http_proxy is not None and http_proxy != "":
            proxy_config["http"] = http_proxy
        elif http_proxy == "":  # 明确传入空字符串表示清空
            proxy_config["http"] = ""
        
        if https_proxy is not None and https_proxy != "":
            proxy_config["https"] = https_proxy
        elif https_proxy == "":  # 明确传入空字符串表示清空
            proxy_config["https"] = ""
            
        if username is not None and username != "":
            proxy_config["username"] = username
        elif username == "":  # 明确传入空字符串表示清空
            proxy_config["username"] = ""
            
        if password is not None and password != "":
            proxy_config["password"] = password
        elif password == "":  # 明确传入空字符串表示清空
            proxy_config["password"] = ""
        
        # 如果设置了代理地址，自动启用代理
        if (http_proxy or https_proxy) and enabled is None:
            proxy_config["enabled"] = True
        
        # 如果清除了所有代理地址，自动禁用代理
        if not proxy_config["http"] and not proxy_config["https"]:
            proxy_config["enabled"] = False
        
        self.save_config(self.config)
        
        if proxy_config["enabled"]:
            print("✅ 代理已启用")
            if proxy_config["http"]:
                print(f"   HTTP代理: {proxy_config['http']}")
            if proxy_config["https"]:
                print(f"   HTTPS代理: {proxy_config['https']}")
            if proxy_config["username"]:
                print(f"   认证用户: {proxy_config['username']}")
        else:
            print("❌ 代理已禁用")
    
    def show_proxy_config(self):
        """显示当前代理配置"""
        proxy_config = self.config.get("proxy", {})
        
        print("当前代理配置:")
        print(f"  启用状态: {'✅ 已启用' if proxy_config.get('enabled', False) else '❌ 已禁用'}")
        print(f"  HTTP代理:  {proxy_config.get('http', '未设置')}")
        print(f"  HTTPS代理: {proxy_config.get('https', '未设置')}")
        print(f"  认证用户:  {proxy_config.get('username', '未设置')}")
        print(f"  认证密码:  {'***' if proxy_config.get('password') else '未设置'}")
    
    def set_email_config(self, smtp_server: str = None, smtp_port: int = None,
                        use_tls: bool = None, username: str = None, password: str = None,
                        from_addr: str = None, to_addr: str = None, enabled: bool = None):
        """设置邮件通知配置"""
        if "notification" not in self.config:
            self.config["notification"] = {
                "enabled": False,
                "email": {}
            }
        
        # 确保email配置是字典类型（兼容旧版本配置）
        if "email" not in self.config["notification"] or not isinstance(self.config["notification"]["email"], dict):
            self.config["notification"]["email"] = {}
        
        email_config = self.config["notification"]["email"]
        
        if smtp_server is not None:
            email_config["smtp_server"] = smtp_server
        if smtp_port is not None:
            email_config["smtp_port"] = smtp_port
        if use_tls is not None:
            email_config["use_tls"] = use_tls
        if username is not None:
            email_config["username"] = username
        if password is not None:
            email_config["password"] = password
        if from_addr is not None:
            email_config["from_addr"] = from_addr
        if to_addr is not None:
            email_config["to_addr"] = to_addr
        
        if enabled is not None:
            self.config["notification"]["enabled"] = enabled
        
        # 如果设置了必要参数，自动启用通知
        if (smtp_server or username or to_addr) and enabled is None:
            if email_config.get("smtp_server") and email_config.get("username") and email_config.get("to_addr"):
                self.config["notification"]["enabled"] = True
        
        self.save_config(self.config)
        
        if self.config["notification"]["enabled"]:
            print("✅ 邮件通知已启用")
            print(f"   SMTP服务器: {email_config.get('smtp_server', '未设置')}")
            print(f"   SMTP端口: {email_config.get('smtp_port', '未设置')}")
            print(f"   发件人: {email_config.get('from_addr', email_config.get('username', '未设置'))}")
            print(f"   收件人: {email_config.get('to_addr', '未设置')}")
        else:
            print("❌ 邮件通知已禁用")
    
    def show_email_config(self):
        """显示当前邮件配置"""
        notification_config = self.config.get("notification", {})
        email_config = notification_config.get("email", {})
        # 兼容旧版本配置（email可能是字符串）
        if not isinstance(email_config, dict):
            email_config = {}
        
        print("当前邮件通知配置:")
        print(f"  通知状态: {'✅ 已启用' if notification_config.get('enabled', False) else '❌ 已禁用'}")
        print(f"  SMTP服务器: {email_config.get('smtp_server', '未设置')}")
        print(f"  SMTP端口: {email_config.get('smtp_port', '未设置')}")
        print(f"  使用TLS: {'是' if email_config.get('use_tls', True) else '否'}")
        print(f"  用户名: {email_config.get('username', '未设置')}")
        print(f"  密码: {'***' if email_config.get('password') else '未设置'}")
        print(f"  发件人: {email_config.get('from_addr', email_config.get('username', '未设置'))}")
        print(f"  收件人: {email_config.get('to_addr', '未设置')}")
    
    def send_email_notification(self, updates: List[Dict]) -> bool:
        """发送邮件通知"""
        if not updates:
            return False
        
        notification_config = self.config.get("notification", {})
        if not notification_config.get("enabled", False):
            return False
        
        email_config = notification_config.get("email", {})
        # 兼容旧版本配置（email可能是字符串）
        if not isinstance(email_config, dict):
            print("邮件配置格式错误，请使用 --set-email 重新配置")
            return False
        
        # 检查必需的配置
        required_fields = ["smtp_server", "username", "password", "to_addr"]
        for field in required_fields:
            if not email_config.get(field):
                print(f"邮件配置不完整，缺少: {field}")
                return False
        
        try:
            # 创建邮件内容
            msg = MIMEMultipart('alternative')
            msg['From'] = Header(email_config.get('from_addr', email_config['username']), 'utf-8')
            msg['To'] = Header(email_config['to_addr'], 'utf-8')
            msg['Subject'] = Header(f'Civitai模型更新通知 - 发现{len(updates)}个更新', 'utf-8')
            
            # 构建HTML邮件内容
            html_content = self._build_email_html(updates)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            # 构建纯文本邮件内容（备用）
            text_content = self._build_email_text(updates)
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # 发送邮件
            smtp_port = email_config.get('smtp_port', 587)
            use_tls = email_config.get('use_tls', True)
            
            if use_tls:
                server = smtplib.SMTP(email_config['smtp_server'], smtp_port, timeout=30)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(email_config['smtp_server'], smtp_port, timeout=30)
            
            server.login(email_config['username'], email_config['password'])
            server.sendmail(
                email_config.get('from_addr', email_config['username']),
                email_config['to_addr'],
                msg.as_string()
            )
            server.quit()
            
            print(f"✅ 邮件通知已发送到: {email_config['to_addr']}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print("❌ 邮件发送失败: 认证失败，请检查用户名和密码")
            return False
        except smtplib.SMTPException as e:
            print(f"❌ 邮件发送失败: SMTP错误 - {e}")
            return False
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")
            return False
    
    def _build_email_html(self, updates: List[Dict]) -> str:
        """构建HTML格式的邮件内容"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px; }}
                .update-item {{ background-color: #f9f9f9; margin: 15px 0; padding: 15px; border-left: 4px solid #4CAF50; border-radius: 3px; }}
                .model-name {{ font-size: 18px; font-weight: bold; color: #2196F3; margin-bottom: 10px; }}
                .version-info {{ margin: 5px 0; }}
                .description {{ margin: 10px 0; padding: 10px; background-color: #fff; border-radius: 3px; }}
                .link {{ color: #2196F3; text-decoration: none; }}
                .link:hover {{ text-decoration: underline; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Civitai模型更新通知</h1>
                    <p>发现 {len(updates)} 个模型有更新</p>
                </div>
        """
        
        for update in updates:
            model_name = update.get('model_name', 'Unknown')
            new_version = update.get('new_version_name', 'Unnamed')
            update_time = update.get('update_time', '')
            description = update.get('description', '无描述')
            model_url = update.get('model_url', '')
            
            # 清理和截断描述
            if len(description) > 300:
                description = description[:300] + "..."
            description = description.replace('<', '&lt;').replace('>', '&gt;')
            
            html += f"""
                <div class="update-item">
                    <div class="model-name">{model_name}</div>
                    <div class="version-info"><strong>新版本:</strong> {new_version}</div>
                    <div class="version-info"><strong>更新时间:</strong> {update_time}</div>
                    <div class="description"><strong>描述:</strong><br>{description}</div>
                    <div class="version-info">
                        <a href="{model_url}" class="link" target="_blank">查看模型详情 →</a>
                    </div>
                </div>
            """
        
        html += """
                <div class="footer">
                    <p>这是一封来自Civitai模型更新检查器的自动通知邮件</p>
                    <p>检查时间: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _build_email_text(self, updates: List[Dict]) -> str:
        """构建纯文本格式的邮件内容"""
        text = f"Civitai模型更新通知\n\n发现 {len(updates)} 个模型有更新:\n\n"
        text += "=" * 60 + "\n\n"
        
        for i, update in enumerate(updates, 1):
            model_name = update.get('model_name', 'Unknown')
            new_version = update.get('new_version_name', 'Unnamed')
            update_time = update.get('update_time', '')
            description = update.get('description', '无描述')
            model_url = update.get('model_url', '')
            
            if len(description) > 200:
                description = description[:200] + "..."
            
            text += f"{i}. {model_name}\n"
            text += f"   新版本: {new_version}\n"
            text += f"   更新时间: {update_time}\n"
            text += f"   描述: {description}\n"
            text += f"   链接: {model_url}\n\n"
        
        text += "=" * 60 + "\n"
        text += f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        text += "\n这是一封来自Civitai模型更新检查器的自动通知邮件\n"
        
        return text
    
    def remove_model(self, model_id_or_alias: str):
        """移除监控的模型"""
        original_count = len(self.config["models"])
        reference = self.extract_model_reference(model_id_or_alias) if "://" in model_id_or_alias else None

        def should_keep_model(model: Dict) -> bool:
            if reference:
                return not (
                    model.get("id") == reference["model_id"] and
                    self.get_model_site(model) == reference["site"]
                )

            return (
                model.get("id") != model_id_or_alias and
                model.get("alias", "") != model_id_or_alias and
                model.get("url", "") != model_id_or_alias
            )

        self.config["models"] = [
            model for model in self.config["models"]
            if should_keep_model(model)
        ]
        
        if len(self.config["models"]) < original_count:
            self.save_config(self.config)
            print(f"已移除模型: {model_id_or_alias}")
            return True
        else:
            print(f"未找到模型: {model_id_or_alias}")
            return False
    
    def list_models(self):
        """列出所有监控的模型"""
        if not self.config["models"]:
            print("当前没有监控任何模型")
            return
        
        print("当前监控的模型:")
        print("-" * 80)
        for i, model in enumerate(self.config["models"], 1):
            print(f"{i}. {model['alias']} (ID: {model['id']}, Site: {self.get_model_site(model)})")
            print(f"   URL: {model['url']}")
            print(f"   添加时间: {model['added_date']}")
            print()
    
    def check_model_updates(self, model: Dict) -> Optional[Dict]:
        """检查单个模型的更新"""
        model_id = model["id"]
        model_site = self.get_model_site(model)
        model_name = model.get("alias", model.get("name", "Unknown"))
        
        print(f"检查模型: {model_name} (ID: {model_id})")
        
        # 获取当前版本信息
        versions = self.get_model_versions(model_id, site=model_site)
        if not versions or len(versions) == 0:
            print(f"  无法获取版本信息")
            return None
        
        # 获取最新版本
        latest_version = versions[0]  # API返回的版本按时间降序排列
        
        # 验证版本数据完整性
        if not isinstance(latest_version, dict) or "id" not in latest_version:
            print(f"  版本数据格式错误")
            return None
        
        # 加载历史记录
        history = self.load_history()
        
        # 检查是否有更新
        if model_id not in history:
            # 首次检查，记录当前最新版本
            history[model_id] = {
                "last_version_id": latest_version["id"],
                "last_version_name": latest_version.get("name", ""),
                "last_check": datetime.now().isoformat(),
                "last_update": latest_version.get("createdAt", "")
            }
            self.save_history(history)
            print(f"  首次检查，记录版本: {latest_version.get('name', 'Unnamed')}")
            return None
        
        # 比较版本
        last_version_id = history[model_id]["last_version_id"]
        if latest_version["id"] != last_version_id:
            # 发现更新
            update_info = {
                "model_id": model_id,
                "model_name": model_name,
                "old_version_id": last_version_id,
                "new_version_id": latest_version["id"],
                "new_version_name": latest_version.get("name", ""),
                "update_time": latest_version.get("createdAt", ""),
                "description": latest_version.get("description", ""),
                "download_url": latest_version.get("downloadUrl", ""),
                "model_url": model["url"]
            }
            
            # 更新历史记录
            history[model_id].update({
                "last_version_id": latest_version["id"],
                "last_version_name": latest_version.get("name", ""),
                "last_check": datetime.now().isoformat(),
                "last_update": latest_version.get("createdAt", "")
            })
            self.save_history(history)
            
            print(f"  🎉 发现更新! 新版本: {latest_version.get('name', 'Unnamed')}")
            return update_info
        else:
            # 更新检查时间
            history[model_id]["last_check"] = datetime.now().isoformat()
            self.save_history(history)
            print(f"  ✅ 没有更新")
            return None
    
    def check_all_updates(self) -> List[Dict]:
        """检查所有模型的更新"""
        updates = []
        
        if not self.config["models"]:
            print("没有要检查的模型")
            return updates
        
        print(f"开始检查 {len(self.config['models'])} 个模型的更新...")
        print("=" * 80)
        
        for model in self.config["models"]:
            try:
                update_info = self.check_model_updates(model)
                if update_info:
                    updates.append(update_info)
                
                # 避免请求太频繁
                time.sleep(1)
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, 
                   requests.exceptions.HTTPError, requests.exceptions.RequestException) as e:
                print(f"检查模型 {model.get('alias', model['id'])} 时网络出错: {e}")
            except Exception as e:
                print(f"检查模型 {model.get('alias', model['id'])} 时发生未知错误: {e}")
        
        print("=" * 80)
        
        if updates:
            print(f"发现 {len(updates)} 个模型有更新:")
            for update in updates:
                print(f"- {update['model_name']}: {update['new_version_name']}")
            
            # 发送邮件通知
            if self.config.get("notification", {}).get("enabled", False):
                print("\n正在发送邮件通知...")
                self.send_email_notification(updates)
        else:
            print("所有模型都是最新版本")
        
        return updates
    
    def run_daemon(self):
        """以守护进程模式运行"""
        interval_hours = self.config.get("check_interval_hours", 24)
        print(f"启动守护进程模式，每 {interval_hours} 小时检查一次")
        
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查更新...")
                updates = self.check_all_updates()
                # 邮件通知已在check_all_updates中处理
                
                print(f"下次检查时间: {(datetime.now() + timedelta(hours=interval_hours)).strftime('%Y-%m-%d %H:%M:%S')}")
                time.sleep(interval_hours * 3600)  # 转换为秒
                
            except KeyboardInterrupt:
                print("\n用户中断，退出守护进程")
                break
            except Exception as e:
                print(f"守护进程运行错误: {e}")
                time.sleep(60)  # 出错后等待1分钟再重试


def main():
    """
    主函数 - 处理命令行参数并执行相应的操作
    """
    parser = argparse.ArgumentParser(description="Civitai模型更新检查器")
    parser.add_argument("--add", help="添加要监控的模型URL")
    parser.add_argument("--alias", help="模型别名")
    parser.add_argument("--remove", help="移除模型（使用ID、别名或完整URL）")
    parser.add_argument("--list", action="store_true", help="列出所有监控的模型")
    parser.add_argument("--check", action="store_true", help="检查所有模型的更新")
    parser.add_argument("--daemon", action="store_true", help="以守护进程模式运行")
    parser.add_argument("--set-api-key", help="设置Civitai API key（可选，用于访问需要认证的功能）")
    
    # 代理相关参数
    parser.add_argument("--set-proxy", action="store_true", help="设置代理服务器")
    parser.add_argument("--proxy-http", help="HTTP代理地址 (如: http://proxy.example.com:8080)")
    parser.add_argument("--proxy-https", help="HTTPS代理地址 (如: https://proxy.example.com:8080)")
    parser.add_argument("--proxy-username", help="代理认证用户名")
    parser.add_argument("--proxy-password", help="代理认证密码")
    parser.add_argument("--enable-proxy", action="store_true", help="启用代理")
    parser.add_argument("--disable-proxy", action="store_true", help="禁用代理")
    parser.add_argument("--show-proxy", action="store_true", help="显示当前代理配置")
    
    # 邮件通知相关参数
    parser.add_argument("--set-email", action="store_true", help="设置邮件通知")
    parser.add_argument("--email-smtp", help="SMTP服务器地址 (如: smtp.gmail.com)")
    parser.add_argument("--email-port", type=int, help="SMTP端口 (如: 587)")
    parser.add_argument("--email-user", help="发件人邮箱账号")
    parser.add_argument("--email-password", help="邮箱密码或应用专用密码")
    parser.add_argument("--email-from", help="发件人地址（可选，默认与user相同）")
    parser.add_argument("--email-to", help="收件人邮箱地址")
    parser.add_argument("--email-tls", action="store_true", help="使用TLS加密")
    parser.add_argument("--email-no-tls", action="store_true", help="不使用TLS加密")
    parser.add_argument("--enable-notification", action="store_true", help="启用邮件通知")
    parser.add_argument("--disable-notification", action="store_true", help="禁用邮件通知")
    parser.add_argument("--show-email", action="store_true", help="显示当前邮件配置")
    parser.add_argument("--test-email", action="store_true", help="发送测试邮件")
    
    args = parser.parse_args()
    
    checker = CivitaiChecker()
    
    if args.add:
        checker.add_model(args.add, args.alias or "")
    elif args.remove:
        checker.remove_model(args.remove)
    elif args.list:
        checker.list_models()
    elif args.check:
        checker.check_all_updates()
    elif args.daemon:
        checker.run_daemon()
    elif args.set_api_key is not None:
        checker.set_api_key(args.set_api_key)
    elif args.set_proxy or args.proxy_http or args.proxy_https or args.proxy_username or args.proxy_password:
        # 设置代理 - 只更新传入的参数，保留未传入的现有配置
        proxy_kwargs = {}
        if args.proxy_http is not None:
            proxy_kwargs["http_proxy"] = args.proxy_http
        if args.proxy_https is not None:
            proxy_kwargs["https_proxy"] = args.proxy_https
        if args.proxy_username is not None:
            proxy_kwargs["username"] = args.proxy_username
        if args.proxy_password is not None:
            proxy_kwargs["password"] = args.proxy_password
        checker.set_proxy(**proxy_kwargs)
    elif args.enable_proxy:
        checker.set_proxy(enabled=True)
    elif args.disable_proxy:
        checker.set_proxy(enabled=False)
    elif args.show_proxy:
        checker.show_proxy_config()
    elif args.set_email or args.email_smtp or args.email_user or args.email_password or args.email_to:
        # 设置邮件配置
        email_kwargs = {}
        if args.email_smtp:
            email_kwargs["smtp_server"] = args.email_smtp
        if args.email_port:
            email_kwargs["smtp_port"] = args.email_port
        if args.email_user:
            email_kwargs["username"] = args.email_user
        if args.email_password:
            email_kwargs["password"] = args.email_password
        if args.email_from:
            email_kwargs["from_addr"] = args.email_from
        if args.email_to:
            email_kwargs["to_addr"] = args.email_to
        if args.email_tls:
            email_kwargs["use_tls"] = True
        elif args.email_no_tls:
            email_kwargs["use_tls"] = False
        checker.set_email_config(**email_kwargs)
    elif args.enable_notification:
        checker.set_email_config(enabled=True)
    elif args.disable_notification:
        checker.set_email_config(enabled=False)
    elif args.show_email:
        checker.show_email_config()
    elif args.test_email:
        # 发送测试邮件
        test_updates = [{
            "model_id": "test",
            "model_name": "测试模型",
            "old_version_id": "old123",
            "new_version_id": "new456",
            "new_version_name": "测试版本 v1.0",
            "update_time": datetime.now().isoformat(),
            "description": "这是一封测试邮件，用于验证邮件通知配置是否正确。",
            "model_url": "https://civitai.com/models/test"
        }]
        if checker.send_email_notification(test_updates):
            print("测试邮件发送成功！")
        else:
            print("测试邮件发送失败，请检查配置。")
    else:
        print("Civitai模型更新检查器")
        print("使用方法:")
        print("  添加模型: python civitai_checker.py --add <URL> [--alias <别名>]")
        print("  移除模型: python civitai_checker.py --remove <ID|别名|完整URL>")
        print("  列出模型: python civitai_checker.py --list")
        print("  检查更新: python civitai_checker.py --check")
        print("  守护进程: python civitai_checker.py --daemon")
        print()
        print("API设置:")
        print("  设置API key: python civitai_checker.py --set-api-key <your_api_key>")
        print("  清除API key: python civitai_checker.py --set-api-key ''")
        print()
        print("代理设置:")
        print("  设置HTTP代理: python civitai_checker.py --proxy-http <proxy_url>")
        print("  设置HTTPS代理: python civitai_checker.py --proxy-https <proxy_url>")
        print("  设置代理认证: python civitai_checker.py --proxy-username <user> --proxy-password <pass>")
        print("  启用代理: python civitai_checker.py --enable-proxy")
        print("  禁用代理: python civitai_checker.py --disable-proxy")
        print("  查看代理配置: python civitai_checker.py --show-proxy")
        print()
        print("邮件通知设置:")
        print("  设置邮件通知: python civitai_checker.py --email-smtp <smtp服务器> --email-port <端口> \\")
        print("                              --email-user <发件邮箱> --email-password <密码> \\")
        print("                              --email-to <收件邮箱> [--email-tls]")
        print("  启用通知: python civitai_checker.py --enable-notification")
        print("  禁用通知: python civitai_checker.py --disable-notification")
        print("  查看邮件配置: python civitai_checker.py --show-email")
        print("  测试邮件发送: python civitai_checker.py --test-email")
        print()
        print("常用SMTP服务器配置示例:")
        print("  Gmail: --email-smtp smtp.gmail.com --email-port 587 --email-tls")
        print("  QQ邮箱: --email-smtp smtp.qq.com --email-port 587 --email-tls")
        print("  163邮箱: --email-smtp smtp.163.com --email-port 465")
        print("  Outlook: --email-smtp smtp-mail.outlook.com --email-port 587 --email-tls")
        print()
        print("注意:")
        print("- 大部分功能不需要API key")
        print("- API key用于访问需要认证的功能（如某些私有模型）")
        print("- 可以在 https://civitai.com/user/account 获取API key")
        print("- 支持的模型站点: https://civitai.com 和 https://civitai.red")
        print("- 代理格式: http://proxy.example.com:8080 或 https://proxy.example.com:8080")
        print("- Gmail需要使用应用专用密码: https://myaccount.google.com/apppasswords")
        print("- QQ邮箱需要开启SMTP服务并使用授权码")


if __name__ == "__main__":
    main()
