#!/usr/bin/env python3
"""
Windows任务计划配置助手
帮助用户设置Windows定时任务来自动运行检查
"""

import os
import subprocess
import sys
from pathlib import Path

def create_scheduled_task():
    """创建Windows计划任务"""
    script_dir = Path(__file__).parent.absolute()
    python_exe = r"C:/Users/xuzhh/AppData/Local/Programs/Python/Python310/python.exe"
    checker_script = script_dir / "civitai_checker.py"
    
    # 任务名称
    task_name = "CivitaiModelChecker"
    
    # 任务命令
    task_command = f'"{python_exe}" "{checker_script}" --check'
    
    # 创建任务的XML配置
    xml_config = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>2025-07-14T12:00:00</Date>
    <Author>CivitaiChecker</Author>
    <Description>每天检查Civitai模型更新</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2025-07-14T09:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>"{checker_script}" --check</Arguments>
      <WorkingDirectory>{script_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''

    # 保存XML文件
    xml_file = script_dir / "task_config.xml"
    with open(xml_file, 'w', encoding='utf-16') as f:
        f.write(xml_config)
    
    print("Windows任务计划配置助手")
    print("=" * 50)
    print(f"已生成任务配置文件: {xml_file}")
    print()
    print("要创建定时任务，请以管理员身份运行以下命令:")
    print(f'schtasks /create /xml "{xml_file}" /tn "{task_name}"')
    print()
    print("或者手动在任务计划程序中创建任务:")
    print("1. 打开'任务计划程序'")
    print("2. 点击'创建基本任务'")
    print("3. 设置任务名称: CivitaiModelChecker")
    print("4. 触发器: 每天")
    print("5. 时间: 每天上午9:00")
    print(f"6. 操作: 启动程序")
    print(f"   程序/脚本: {python_exe}")
    print(f"   参数: \"{checker_script}\" --check")
    print(f"   起始于: {script_dir}")
    
    # 提供删除任务的命令
    print()
    print("要删除任务，请运行:")
    print(f'schtasks /delete /tn "{task_name}" /f')
    
    return xml_file

if __name__ == "__main__":
    try:
        xml_file = create_scheduled_task()
        
        # 询问是否要立即创建任务
        response = input("\n是否要尝试立即创建任务？(需要管理员权限) [y/N]: ")
        if response.lower() in ['y', 'yes']:
            try:
                cmd = f'schtasks /create /xml "{xml_file}" /tn "CivitaiModelChecker"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    print("✅ 任务创建成功!")
                else:
                    print(f"❌ 任务创建失败: {result.stderr}")
                    print("请确保以管理员身份运行此脚本")
            except Exception as e:
                print(f"❌ 创建任务时出错: {e}")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
