#!/usr/bin/env python3
"""
错误诊断脚本 - 检查程序可能的问题
"""

import sys
import os
import json
import requests
from pathlib import Path


def get_data_dir(script_dir: Path) -> Path:
    """获取当前生效的数据目录"""
    data_dir = os.environ.get("CIVITAI_CHECKER_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir)
    return script_dir

def check_python_version():
    """检查Python版本"""
    print("=== Python版本检查 ===")
    print(f"Python版本: {sys.version}")
    if sys.version_info < (3, 6):
        print("❌ Python版本过低，建议使用Python 3.6+")
        return False
    else:
        print("✅ Python版本正常")
        return True

def check_dependencies():
    """检查依赖包"""
    print("\n=== 依赖包检查 ===")
    required_packages = ['requests', 'json', 'os', 'time', 'datetime', 'typing', 'argparse']
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - 正常")
        except ImportError:
            print(f"❌ {package} - 缺失")
            if package == 'requests':
                print("   请运行: pip install requests")
            return False
    return True

def check_files():
    """检查文件完整性"""
    print("\n=== 文件完整性检查 ===")
    script_dir = Path(__file__).parent
    required_files = [
        'civitai_checker.py',
        'requirements.txt',
        'README.md',
        'Dockerfile',
        'docker-compose.yml',
        'tests/test_civitai_checker.py'
    ]
    
    all_good = True
    for file_name in required_files:
        file_path = script_dir / file_name
        if file_path.exists():
            print(f"✅ {file_name} - 存在")
        else:
            print(f"❌ {file_name} - 缺失")
            all_good = False
    
    return all_good

def check_config_files():
    """检查配置文件"""
    print("\n=== 配置文件检查 ===")
    script_dir = Path(__file__).parent
    data_dir = get_data_dir(script_dir)
    print(f"当前数据目录: {data_dir}")
    
    # 检查config.json
    config_file = data_dir / "config.json"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print("✅ config.json - 格式正确")
            print(f"   监控模型数量: {len(config.get('models', []))}")
            print(f"   检查间隔: {config.get('check_interval_hours', 24)}小时")
            print(f"   API key: {'已设置' if config.get('api_key') else '未设置'}")
        except Exception as e:
            print(f"❌ config.json - 格式错误: {e}")
            return False
    else:
        print("ℹ️  config.json - 不存在（首次运行时会自动创建）")
    
    # 检查历史文件
    history_file = data_dir / "model_history.json"
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            print("✅ model_history.json - 格式正确")
            print(f"   历史记录数量: {len(history)}")
        except Exception as e:
            print(f"❌ model_history.json - 格式错误: {e}")
    else:
        print("ℹ️  model_history.json - 不存在（首次检查后会自动创建）")
    
    return True

def check_network():
    """检查网络连接"""
    print("\n=== 网络连接检查 ===")

    api_targets = [
        ("civitai.com", "https://civitai.com/api/v1/models/4384"),
        ("civitai.red", "https://civitai.red/api/v1/models/4384"),
    ]

    all_good = True
    for site_name, api_url in api_targets:
        try:
            response = requests.get(api_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {site_name} API连接 - 正常")
                print(f"   测试模型: {data.get('name', 'Unknown')}")
            else:
                print(f"❌ {site_name} API连接 - HTTP {response.status_code}")
                all_good = False
        except Exception as e:
            print(f"❌ {site_name} API连接 - 失败: {e}")
            all_good = False

    return all_good

def check_permissions():
    """检查文件权限"""
    print("\n=== 文件权限检查 ===")
    script_dir = Path(__file__).parent
    
    # 检查读写权限
    try:
        test_file = script_dir / "test_permissions.tmp"
        with open(test_file, 'w') as f:
            f.write("test")
        test_file.unlink()
        print("✅ 文件读写权限 - 正常")
        return True
    except Exception as e:
        print(f"❌ 文件读写权限 - 失败: {e}")
        return False

def run_syntax_check():
    """检查语法错误"""
    print("\n=== 语法检查 ===")
    script_dir = Path(__file__).parent
    main_script = script_dir / "civitai_checker.py"
    
    if not main_script.exists():
        print("❌ civitai_checker.py 不存在")
        return False
    
    try:
        with open(main_script, 'r', encoding='utf-8') as f:
            code = f.read()
        
        compile(code, str(main_script), 'exec')
        print("✅ 语法检查 - 通过")
        return True
    except SyntaxError as e:
        print(f"❌ 语法错误: 第{e.lineno}行 - {e.msg}")
        return False
    except Exception as e:
        print(f"❌ 语法检查失败: {e}")
        return False

def main():
    print("Civitai模型检查器 - 错误诊断")
    print("=" * 50)
    
    checks = [
        ("Python版本", check_python_version),
        ("依赖包", check_dependencies),
        ("文件完整性", check_files),
        ("配置文件", check_config_files),
        ("网络连接", check_network),
        ("文件权限", check_permissions),
        ("语法检查", run_syntax_check)
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ {check_name}检查时出错: {e}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ 所有检查通过！程序应该可以正常运行。")
        print("\n如果仍然遇到问题，请检查:")
        print("1. 防火墙是否阻止了网络连接")
        print("2. 代理设置是否正确")
        print("3. 是否有其他安全软件干扰")
    else:
        print("❌ 检查发现问题，请根据上述提示修复后重试。")
        print("\n常见解决方案:")
        print("1. 运行: pip install -r requirements.txt")
        print("2. 检查网络连接和防火墙设置")
        print("3. 确保有足够的磁盘空间和权限")

if __name__ == "__main__":
    main()
