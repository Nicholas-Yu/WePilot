#!/usr/bin/env python3
"""
进程锁功能测试脚本
"""
import os
import sys
import time
import signal
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_single_instance():
    """测试单实例功能"""
    print("=" * 60)
    print("测试 1: 单实例检查")
    print("=" * 60)
    
    # 清理可能存在的旧 PID 文件
    pid_file = Path("data/bot.pid")
    if pid_file.exists():
        pid_file.unlink()
        print("✅ 已清理旧的 PID 文件")
    
    # 模拟检查单实例
    from bot import check_single_instance
    
    # 第一次检查 - 应该通过
    result1 = check_single_instance()
    print(f"首次检查结果: {'通过' if result1 else '失败'}")
    assert result1, "首次检查应该通过"
    
    # 第二次检查 - 应该失败
    result2 = check_single_instance()
    print(f"重复检查结果: {'失败（预期）' if not result2 else '通过（意外）'}")
    assert not result2, "重复检查应该失败"
    
    # 清理
    from bot import cleanup_pid_file
    cleanup_pid_file()
    print("✅ 单实例测试通过")
    print()

def test_pid_file_format():
    """测试 PID 文件格式"""
    print("=" * 60)
    print("测试 2: PID 文件格式")
    print("=" * 60)
    
    pid_file = Path("data/bot.pid")
    
    # 模拟创建 PID 文件
    from bot import check_single_instance, cleanup_pid_file
    check_single_instance()
    
    # 验证文件内容
    assert pid_file.exists(), "PID 文件应该存在"
    pid_content = pid_file.read_text().strip()
    current_pid = os.getpid()
    print(f"当前进程 PID: {current_pid}")
    print(f"PID 文件内容: {pid_content}")
    assert int(pid_content) == current_pid, "PID 文件内容应该与当前进程一致"
    
    # 清理
    cleanup_pid_file()
    print("✅ PID 文件格式测试通过")
    print()

def test_cleanup():
    """测试清理功能"""
    print("=" * 60)
    print("测试 3: 清理功能")
    print("=" * 60)
    
    from bot import check_single_instance, cleanup_pid_file
    
    # 创建 PID 文件
    check_single_instance()
    pid_file = Path("data/bot.pid")
    assert pid_file.exists(), "PID 文件应该存在"
    
    # 清理
    cleanup_pid_file()
    assert not pid_file.exists(), "PID 文件应该被清理"
    
    print("✅ 清理功能测试通过")
    print()

def test_invalid_pid_file():
    """测试损坏的 PID 文件"""
    print("=" * 60)
    print("测试 4: 损坏的 PID 文件处理")
    print("=" * 60)
    
    from bot import check_single_instance, cleanup_pid_file, PID_FILE
    
    # 创建损坏的 PID 文件
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text("not_a_number")
    
    # 检查是否能处理
    result = check_single_instance()
    assert result, "应该能处理损坏的 PID 文件并继续启动"
    
    # 清理
    cleanup_pid_file()
    print("✅ 损坏 PID 文件处理测试通过")
    print()

def test_stale_pid_file():
    """测试过期的 PID 文件（进程已不存在）"""
    print("=" * 60)
    print("测试 5: 过期的 PID 文件处理")
    print("=" * 60)
    
    from bot import check_single_instance, cleanup_pid_file, PID_FILE
    
    # 创建一个已不存在的进程 PID
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text("1")  # PID 1 通常是 launchd，不会是我们的进程
    
    # 检查是否自动清理
    result = check_single_instance()
    assert result, "应该能检测到过期 PID 并继续启动"
    print("✅ 过期的 PID 文件处理测试通过")
    print()

def main():
    print("\n" + "=" * 60)
    print("微信机器人进程锁功能测试")
    print("=" * 60 + "\n")
    
    try:
        test_single_instance()
        test_pid_file_format()
        test_cleanup()
        test_invalid_pid_file()
        test_stale_pid_file()
        
        print("=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
