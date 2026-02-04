#!/usr/bin/env python3
# 测试登录功能，获取详细错误信息

import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from booking_core import setup_browser_and_login

def main():
    print('开始测试登录功能...')
    try:
        driver = setup_browser_and_login()
        if driver:
            print('登录测试成功！')
            driver.quit()
        else:
            print('登录测试失败：返回了None')
    except Exception as e:
        print(f'登录测试出错：{e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
