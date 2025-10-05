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


class CivitaiChecker:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.base_url = "https://civitai.com/api/v1"
        self.config = self.load_config()
        self.history_file = "model_history.json"
        self.api_key = self.config.get("api_key", "")
        
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
                    "email": ""
                }
            }
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Dict):
        """保存配置文件"""
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
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    
    def extract_model_id(self, url: str) -> Optional[str]:
        """从URL中提取模型ID"""
        # 支持多种URL格式
        # https://civitai.com/models/12345
        # https://civitai.com/models/12345/model-name
        try:
            if "civitai.com/models/" in url:
                parts = url.split("/models/")[1].split("/")
                model_id = parts[0]
                # 验证model_id是数字
                if model_id.isdigit():
                    return model_id
                else:
                    print(f"无效的模型ID: {model_id}")
                    return None
            else:
                print("URL格式不正确，应该包含 'civitai.com/models/'")
                return None
        except (IndexError, AttributeError) as e:
            print(f"URL解析错误: {e}")
            return None
    
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
    
    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """获取模型信息"""
        url = f"{self.base_url}/models/{model_id}"
        result = self._make_request(url)
        if result is None:
            print(f"获取模型 {model_id} 信息失败")
        return result
    
    def get_model_versions(self, model_id: str) -> List[Dict]:
        """获取模型版本列表"""
        # 先尝试从模型详情中获取版本信息
        model_info = self.get_model_info(model_id)
        if model_info and "modelVersions" in model_info:
            return model_info["modelVersions"]
        
        # 如果没有版本信息，尝试直接版本API
        url = f"{self.base_url}/models/{model_id}/versions"
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
        model_id = self.extract_model_id(model_url)
        if not model_id:
            print("无效的模型URL")
            return False
        
        # 获取模型信息验证
        model_info = self.get_model_info(model_id)
        if not model_info:
            print("无法获取模型信息，请检查URL是否正确")
            return False
        
        # 添加到配置
        model_entry = {
            "id": model_id,
            "url": model_url,
            "name": model_info.get("name", "Unknown"),
            "alias": alias or model_info.get("name", "Unknown"),
            "added_date": datetime.now().isoformat()
        }
        
        # 检查是否已存在
        for model in self.config["models"]:
            if model["id"] == model_id:
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
    
    def remove_model(self, model_id_or_alias: str):
        """移除监控的模型"""
        original_count = len(self.config["models"])
        self.config["models"] = [
            model for model in self.config["models"]
            if model["id"] != model_id_or_alias and model.get("alias", "") != model_id_or_alias
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
            print(f"{i}. {model['alias']} (ID: {model['id']})")
            print(f"   URL: {model['url']}")
            print(f"   添加时间: {model['added_date']}")
            print()
    
    def check_model_updates(self, model: Dict) -> Optional[Dict]:
        """检查单个模型的更新"""
        model_id = model["id"]
        model_name = model.get("alias", model.get("name", "Unknown"))
        
        print(f"检查模型: {model_name} (ID: {model_id})")
        
        # 获取当前版本信息
        versions = self.get_model_versions(model_id)
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
                
                if updates:
                    # 这里可以添加通知逻辑（邮件、微信等）
                    pass
                
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
    parser.add_argument("--remove", help="移除模型（使用ID或别名）")
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
    else:
        print("Civitai模型更新检查器")
        print("使用方法:")
        print("  添加模型: python civitai_checker.py --add <URL> [--alias <别名>]")
        print("  移除模型: python civitai_checker.py --remove <ID或别名>")
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
        print("注意:")
        print("- 大部分功能不需要API key")
        print("- API key用于访问需要认证的功能（如某些私有模型）")
        print("- 可以在 https://civitai.com/user/account 获取API key")
        print("- 代理格式: http://proxy.example.com:8080 或 https://proxy.example.com:8080")


if __name__ == "__main__":
    main()
