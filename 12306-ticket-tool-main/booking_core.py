"""
鲸介12306 抢票助手 - 核心逻辑模块
从原 12306_booking_script.py 重构而来，供 GUI 调用

开发者：鲸介 (Whale_DIY)
项目：Auto12306 智能抢票系统
开源协议：MIT License
"""
import re
import time
import random
import logging
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime

# 配置日志记录
# 创建文件处理器，记录所有级别的日志
file_handler = logging.FileHandler('12306_booking.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))

# 创建控制台处理器，只显示INFO及以上级别的日志
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))

# 配置根日志记录器
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# 钉钉机器人配置
dingtalk_token = ''
dingtalk_secret = ''


def send_dingtalk_notification(title, content, token=None, secret=None):
    """发送钉钉机器人通知"""
    global dingtalk_token, dingtalk_secret
    if not token and not dingtalk_token:
        logger.info('未配置钉钉机器人token，跳过通知发送')
        return False
    
    access_token = token or dingtalk_token
    access_secret = secret or dingtalk_secret
    timestamp = str(int(round(time.time() * 1000)))
    
    # 生成签名
    if access_secret:
        secret_enc = access_secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{access_secret}'.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign, digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        url = f"https://oapi.dingtalk.com/robot/send?access_token={access_token}&timestamp={timestamp}&sign={sign}"
    else:
        url = f"https://oapi.dingtalk.com/robot/send?access_token={access_token}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content
        }
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
        result = response.json()
        if result.get('errcode') == 0:
            logger.info('钉钉通知发送成功')
            return True
        else:
            logger.error(f'钉钉通知发送失败: {result.get("errmsg")}')
            return False
    except Exception as e:
        logger.error(f'发送钉钉通知时出错: {e}', exc_info=True)
        return False


def set_dingtalk_token(token, secret=None):
    """设置钉钉机器人token和secret"""
    global dingtalk_token, dingtalk_secret
    dingtalk_token = token
    if secret:
        dingtalk_secret = secret
        logger.info(f'已设置钉钉机器人token: {token[:20]}... 和 secret: {secret[:20]}...')
    else:
        logger.info(f'已设置钉钉机器人token: {token[:20]}...')


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import Select


def parse_hhmm_to_minutes(hhmm):
    """将 HH:MM 格式转换为分钟数"""
    try:
        h, m = map(int, hhmm.split(':'))
        return h*60 + m
    except Exception:
        return None


def time_in_range(t, start, end):
    """判断时间是否在范围内"""
    tm = parse_hhmm_to_minutes(t)
    sm = parse_hhmm_to_minutes(start)
    em = parse_hhmm_to_minutes(end)
    if None in (tm, sm, em):
        return False
    return sm <= tm <= em


def extract_depart_time_from_row(row):
    """从表格行中提取出发时间"""
    try:
        cand = row.find_elements(
            By.XPATH,
            ".//td[position()=2 or contains(@class,'cdz') or contains(@class,'cds')]//*[self::strong or self::span or self::div or self::em]"
        )
        for c in cand:
            t = (c.text or '').strip()
            if re.fullmatch(r'([01]\d|2[0-3]):([0-5]\d)', t):
                return t
    except Exception:
        pass
    
    try:
        txt = row.text or ''
        m = re.search(r'(?:^|\s)([01]\d|2[0-3]):([0-5]\d)(?:\s|$)', txt)
        if m:
            return f"{m.group(1)}:{m.group(2)}"
    except Exception:
        pass
    
    return None


def extract_train_number_from_row(row):
    """从表格行中提取车次号"""
    try:
        cand = row.find_elements(By.XPATH, ".//td[1]//*[self::strong or self::span or self::a or self::div]")
        for c in cand:
            t = (c.text or '').strip().upper()
            if re.fullmatch(r'[GDKCTZXYFS]\d{1,5}', t):
                return t
        txt = (row.text or '').upper()
        m = re.search(r'\b([GDKCTZXYFS]\d{1,5})\b', txt)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def click_book_in_row(row, driver):
    """点击表格行中的预订按钮"""
    try:
        btns = row.find_elements(By.XPATH, ".//a[contains(text(),'预订')]")
        if not btns:
            logger.info('未找到预订按钮，该车次可能暂无票')
            return False
        btn = btns[0]
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", btn)
        time.sleep(0.2)
        try:
            btn.click()
            logger.info('成功点击预订按钮')
            return True
        except Exception:
            driver.execute_script('arguments[0].click();', btn)
            logger.info('成功点击预订按钮（使用JavaScript）')
            return True
    except Exception as e:
        logger.error(f'点击预订失败: {e}', exc_info=True)
        return False


def _find_rows(driver):
    """获取查询结果表格的所有有效数据行"""
    xpath = "//*[@id='queryLeftTable']/tr[not(contains(@class,'ticket-hd')) and not(contains(@style,'display: none'))]"
    return driver.find_elements(By.XPATH, xpath)


def _find_row_by_train_number(driver, target):
    """根据车次号查找对应的表格行"""
    target = (target or '').strip().upper()
    if not target:
        return None
    try:
        nodes = driver.find_elements(By.XPATH, f"//*[@id='queryLeftTable']//a[normalize-space(text())='{target}']/ancestor::tr[1]")
        for n in nodes:
            if n.is_displayed():
                return n
    except Exception:
        pass
    try:
        rows = _find_rows(driver)
        for r in rows:
            tn = extract_train_number_from_row(r)
            if tn == target:
                return r
    except Exception:
        pass
    return None


def book_by_time_range(driver, start_hhmm, end_hhmm, max_attempts=30, refresh_interval=(3,6)):
    """按时间范围抢票"""
    for attempt in range(1, max_attempts+1):
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'queryLeftTable')))
            rows = _find_rows(driver)
            found_times = []
            candidates = []
            for r in rows:
                dep = extract_depart_time_from_row(r)
                if dep:
                    found_times.append(dep)
                if dep and time_in_range(dep, start_hhmm, end_hhmm):
                    if r.find_elements(By.XPATH, ".//a[contains(text(),'预订')]"):
                        candidates.append((dep, r))
            if candidates:
                candidates.sort(key=lambda x: parse_hhmm_to_minutes(x[0]))
                dep, row = candidates[0]
                logger.info(f'发现时间匹配的车次: {dep}，尝试预订...')
                if click_book_in_row(row, driver):
                    return f'成功尝试预订出发时间 {dep} 的车次'
            else:
                if attempt == 1 or attempt % 5 == 0:
                    preview = ','.join(sorted(set(found_times))[:6]) if found_times else '无'
                    logger.info(f'本次共扫描 {len(rows)} 行，解析到出发时刻: {preview}；未命中范围 {start_hhmm}-{end_hhmm}')
        except Exception as e:
            logger.error(f'第{attempt}次尝试失败: {e}', exc_info=True)
        
        if attempt < max_attempts:
            try:
                refresh_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, 'query_ticket')))
                refresh_btn.click()
            except Exception as e:
                logger.error(f'点击查询按钮刷新失败: {e}，尝试整页刷新')
                driver.refresh()
            wait_time = random.uniform(*refresh_interval)
            logger.info(f'无匹配结果，等待{wait_time:.2f}s后重试...')
            time.sleep(wait_time)
    return '没抢到，可惜~'


def book_by_train_number(driver, target_train_number, max_attempts=0, refresh_interval=(2,4), 
                       params=None, start_time=None, monitor_count_ref=None, last_notification_time=None):
    """按指定车次抢票"""
    target = (target_train_number or '').strip().upper()
    if not target:
        return '未设置目标车次'
    
    # 初始化监控计数
    if monitor_count_ref is None:
        monitor_count_ref = {'count': 0}
    
    # 初始化最后通知时间
    if last_notification_time is None:
        last_notification_time = datetime.now()
    
    # 如果max_attempts为0，则无限监控
    attempt = 0
    while True:
        attempt += 1
        monitor_count_ref['count'] += 1
        if max_attempts > 0 and attempt > max_attempts:
            break
        
        # 每30分钟发送一次状态通知
        current_time = datetime.now()
        if start_time:
            elapsed_minutes = (current_time - last_notification_time).total_seconds() / 60
            if elapsed_minutes >= 30:
                running_time = (current_time - start_time).total_seconds() / 60
                content = f"## 抢票任务运行状态\n" \
                         f"> 已运行时间: {running_time:.1f}分钟\n" \
                         f"> 监控次数: {monitor_count_ref['count']}\n" \
                         f"> 目标车次: {target}\n" \
                         f"> 出发站: {params.get('from_station', '未知')}\n" \
                         f"> 到达站: {params.get('to_station', '未知')}\n" \
                         f"> 日期: {params.get('travel_date', '未知')}\n" \
                         f"> 席别: {params.get('seat_category', '未知')}\n" \
                         f"> 乘车人: {params.get('passenger_name', '未知')}\n" \
                         f"> 状态: 正常监控中\n" \
                         f"> 检查时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                send_dingtalk_notification('抢票任务运行状态', content, params.get('dingtalk_token') if params else None)
                last_notification_time = current_time
        
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'queryLeftTable')))
            row = _find_row_by_train_number(driver, target)
            if row is not None:
                logger.info(f'发现目标车次 {target}，检查是否有票...')
                # 检查是否有预订按钮
                booking_buttons = row.find_elements(By.XPATH, ".//a[contains(text(),'预订')]")
                if booking_buttons:
                    logger.info(f'发现目标车次 {target}，尝试预订...')
                    if click_book_in_row(row, driver):
                        # 发送成功通知
                        content = f"## 抢票成功\n" \
                                 f"> 车次: {target}\n" \
                                 f"> 出发站: {params.get('from_station', '未知')}\n" \
                                 f"> 到达站: {params.get('to_station', '未知')}\n" \
                                 f"> 日期: {params.get('travel_date', '未知')}\n" \
                                 f"> 席别: {params.get('seat_category', '未知')}\n" \
                                 f"> 乘车人: {params.get('passenger_name', '未知')}\n" \
                                 f"> 时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                                 f"> 操作: 已成功点击预订按钮\n"
                        send_dingtalk_notification('抢票成功', content, params.get('dingtalk_token') if params else None)
                        return f'成功尝试预订指定车次 {target}'
                else:
                    logger.info(f'目标车次 {target} 暂无票或不可预订，继续监控...')
            else:
                logger.info(f'未找到目标车次 {target}，继续监控...')
        except Exception as e:
            logger.error(f'第{attempt}次尝试失败: {e}', exc_info=True)
            # 发送失败通知
            content = f"## 监控异常\n" \
                     f"> 车次: {target}\n" \
                     f"> 错误: {str(e)[:100]}\n" \
                     f"> 时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            send_dingtalk_notification('监控异常', content, params.get('dingtalk_token') if params else None)
        
        try:
            refresh_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, 'query_ticket')))
            refresh_btn.click()
        except Exception as e:
            logger.error(f'点击查询按钮刷新失败: {e}，尝试整页刷新')
            driver.refresh()
        wait_time = random.uniform(*refresh_interval)
        logger.info(f'继续监控车次 {target}，等待{wait_time:.2f}s后重试...')
        time.sleep(wait_time)
    # 如果设置了max_attempts且超过限制，才返回结束消息
    return f'监控结束，未抢到指定车次 {target}，可惜~'


def select_seat_fast(driver, preferred_type="first"):
    """快速选座"""
    logger.info(f"快速选择座位，偏好: {preferred_type}")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'seat-sel-bd'))
        )
    except Exception as e:
        logger.error(f'座位选择对话框加载失败: {e}', exc_info=True)
        return False
    try:
        seats = driver.find_elements(By.XPATH, "//div[@class='seat-sel-bd']//a[contains(@href, 'javascript:')]")
        if not seats:
            logger.debug('未找到可选座位')
            return False
        seats[0].click()
        logger.info('已快速选择一个座位')
        return True
    except Exception as e:
        logger.error(f'快速选座失败: {e}', exc_info=True)
        return False


def setup_browser_and_login():
    """设置浏览器并完成登录（供预登录使用）"""
    edge_options = Options()
    edge_options.add_experimental_option('detach', True)
    edge_options.add_argument('--disable-blink-features=AutomationControlled')
    edge_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.3485.54')
    edge_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    # 添加网络相关的参数
    edge_options.add_argument('--no-proxy-server')
    edge_options.add_argument('--disable-extensions')
    edge_options.add_argument('--disable-gpu')
    edge_options.add_argument('--no-sandbox')
    edge_options.add_argument('--disable-dev-shm-usage')
    edge_options.add_argument('--ignore-certificate-errors')
    edge_options.add_argument('--ignore-ssl-errors')
    
    try:
        # 使用Selenium 4.6+的内置驱动管理功能，直接初始化Edge浏览器
        print('正在初始化Edge浏览器...')
        driver = webdriver.Edge(options=edge_options)
        print('成功初始化Edge浏览器')
    except Exception as e:
        print(f'初始化浏览器时出错: {e}')
        print('❌ 无法初始化浏览器')
        print('提示：可能是Edge WebDriver未安装或版本不匹配')
        print('请确保已安装与Edge浏览器版本匹配的WebDriver')
        print('手动下载地址：https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/')
        return None
    
    try:
        driver.get('https://www.12306.cn')
        driver.maximize_window()
        logger.info('✓ 已打开12306官网')
        
        time.sleep(2)
        
        # 登录流程
        try:
            logger.info('正在查找登录按钮...')
            try:
                login_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'J-btn-login')))
                login_button.click()
                logger.info('✓ 已点击登录按钮')
            except Exception as e:
                logger.debug(f'登录按钮查找失败（ID方式）: {e}')
                login_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'登录') or contains(@class,'login')]"))
                )
                login_button.click()
                logger.info('✓ 已点击登录按钮')
        except Exception as e:
            logger.warning(f'⚠ 点击登录按钮失败：{e}')
            logger.warning('提示：请手动点击页面上的"登录"按钮')
            time.sleep(3)
        
        try:
            logger.info('正在切换到扫码登录...')
            try:
                scan_login_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[text()='扫码登录' or contains(text(),'扫码')]"))
                )
                scan_login_button.click()
                logger.info('✓ 已切换到扫码登录')
            except Exception as e:
                logger.debug(f'扫码登录按钮查找失败: {e}')
                logger.info('提示：可能已在扫码登录页面')
        except Exception as e:
            logger.warning(f'⚠ 切换扫码登录失败：{e}')
            logger.warning('提示：请手动点击"扫码登录"按钮')
            time.sleep(2)
        
        logger.info('\n📱 请用手机12306 APP扫码登录...')
        logger.info('⏳ 等待扫码中...\n')
        
        # 等待登录成功
        login_success = False
        for i in range(60):
            try:
                try:
                    WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.XPATH, "//a[text()='个人中心' or contains(text(),'个人')]")))
                    login_success = True
                    break
                except Exception as e:
                    logger.debug(f'个人中心元素查找失败: {e}')
                    if driver.find_elements(By.XPATH, "//*[contains(@class,'user') or contains(@id,'user')]"):
                        login_success = True
                        break
            except Exception as e:
                logger.debug(f'登录状态检查失败: {e}')
                pass
            
            if i % 10 == 0 and i > 0:
                logger.info(f'仍在等待扫码... ({i}秒)')
            time.sleep(1)
        
        if not login_success:
            logger.error('❌ 登录超时')
            logger.error('提示：请确保已用12306 APP扫码并确认登录')
            driver.quit()
            return None
        
        logger.info('✓ 登录成功！')
        return driver
    
    except Exception as e:
        logger.error(f'登录过程出错: {e}', exc_info=True)
        try:
            driver.quit()
        except Exception as quit_error:
            logger.debug(f'关闭浏览器失败: {quit_error}')
            pass
        return None


def run_booking_with_driver(driver, params):
    """使用已登录的浏览器实例执行抢票（供GUI调用）"""
    if not driver:
        logger.error('❌ 浏览器实例无效')
        # 发送失败通知
        content = f"## 抢票任务失败\n" \
                 f"> 失败原因: 浏览器实例无效\n" \
                 f"> 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        send_dingtalk_notification('抢票任务失败', content, params.get('dingtalk_token'))
        return
    
    # 设置钉钉机器人token和secret
    if params.get('dingtalk_token'):
        set_dingtalk_token(params['dingtalk_token'], params.get('dingtalk_secret'))
    
    logger.info('=' * 60)
    logger.info('🚄 桃叔12306 抢票助手 - 开始抢票')
    logger.info('=' * 60)
    logger.info(f"出发站: {params['from_station']} → 到达站: {params['to_station']}")
    logger.info(f"日期: {params['travel_date']} | 票型: {params['ticket_type']}")
    if params.get('target_train_number'):
        logger.info(f"策略: 指定车次 [{params['target_train_number']}]")
    else:
        tr = params['depart_time_range']
        logger.info(f"策略: 时间范围 [{tr['start']} - {tr['end']}]")
    logger.info(f"席别: {params.get('seat_category', '未设置')}")
    logger.info(f"乘车人: {params.get('passenger_name', '未设置')}")
    logger.info('=' * 60)
    
    # 发送开始抢票通知
    start_time = datetime.now()
    if params.get('target_train_number'):
        content = f"## 抢票任务开始\n" \
                 f"> 出发站: {params['from_station']}\n" \
                 f"> 到达站: {params['to_station']}\n" \
                 f"> 日期: {params['travel_date']}\n" \
                 f"> 票型: {params['ticket_type']}\n" \
                 f"> 席别: {params.get('seat_category', '未设置')}\n" \
                 f"> 乘车人: {params.get('passenger_name', '未设置')}\n" \
                 f"> 车次: {params['target_train_number']}\n" \
                 f"> 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    else:
        tr = params['depart_time_range']
        content = f"## 抢票任务开始\n" \
                 f"> 出发站: {params['from_station']}\n" \
                 f"> 到达站: {params['to_station']}\n" \
                 f"> 日期: {params['travel_date']}\n" \
                 f"> 票型: {params['ticket_type']}\n" \
                 f"> 席别: {params.get('seat_category', '未设置')}\n" \
                 f"> 乘车人: {params.get('passenger_name', '未设置')}\n" \
                 f"> 时间范围: {tr['start']} - {tr['end']}\n" \
                 f"> 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    send_dingtalk_notification('抢票任务开始', content, params.get('dingtalk_token'))
    
    # 记录监控次数
    monitor_count = 0
    last_notification_time = start_time
    
    try:
        # 进入购票页面
        try:
            ticket_link = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, 'link_for_ticket')))
            ticket_link.click()
            time.sleep(0.2)
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
            logger.info('✓ 已进入购票页面')
        except Exception as e:
            logger.error(f'进入购票页面失败：{e}', exc_info=True)
            return
        
        # 填写出发站
        try:
            from_station_input = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, 'fromStationText')))
            from_station_input.click()
            from_station_input.clear()
            from_station_input.send_keys(params['from_station'])
            logger.info(f"✓ 已输入出发地: {params['from_station']}")
            first_option = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#citem_0 > span:nth-child(1)')))
            first_option.click()
        except Exception as e:
            logger.error(f'操作出发地输入框失败：{e}', exc_info=True)
            return
        
        # 填写到达站
        try:
            to_station_input = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, 'toStationText')))
            to_station_input.click()
            to_station_input.clear()
            to_station_input.send_keys(params['to_station'])
            logger.info(f"✓ 已输入目的地: {params['to_station']}")
            first_option = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#citem_0 > span:nth-child(1)')))
            first_option.click()
        except Exception as e:
            logger.error(f'操作目的地输入框失败：{e}', exc_info=True)
            return
        
        # 填写出发日期
        try:
            date_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'train_date')))
            date_input.click()
            date_input.clear()
            date_input.send_keys(params['travel_date'])
            logger.info(f"✓ 已输入出发时间: {params['travel_date']}")
            try:
                driver.find_element(By.CLASS_NAME, 'cal').click()
            except Exception as e:
                logger.debug(f'点击日历失败: {e}')
                pass
        except Exception as e:
            logger.error(f'时间输入框操作失败：{e}', exc_info=True)
            return
        
        # 选择票型
        try:
            if params['ticket_type'] == 'student':
                WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, 'sf2'))).click()
                logger.info('✓ 已选择学生票')
            else:
                WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, 'sf1'))).click()
                logger.info('✓ 已选择成人票')
        except Exception as e:
            logger.error(f'票种选择失败：{e}', exc_info=True)
            return
        
        # 等待开售时间
        try:
            bst = (params.get('booking_start_time') or '').strip()
            if bst:
                start_datetime = datetime.strptime(bst, '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                if now < start_datetime:
                    wait_seconds = (start_datetime - now).total_seconds()
                    logger.info(f'等待开售时间，还需 {wait_seconds:.1f} 秒...')
                    if wait_seconds > 10:
                        time.sleep(max(0, wait_seconds - 10))
                    while datetime.now() < start_datetime:
                        time.sleep(0.05)
            logger.info('🚀 到达抢票时间，开始抢票！')
        except Exception as e:
            logger.error(f'时间处理出错: {e}', exc_info=True)
            return
        
        # 第一次查询
        try:
            query_button = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, 'query_ticket')))
            query_button.click()
            logger.info('✓ 已提交查询，正在等待结果...')
            time.sleep(0.2)
        except Exception as e:
            logger.error(f'查询失败：{e}', exc_info=True)
            return
        
        # 执行抢票策略
        ttn = (params.get('target_train_number') or '').strip().upper()
        if ttn:
            logger.info(f'策略：指定车次 [{ttn}]')
            # 设置max_attempts=0，实现无限期监控
            result_msg = book_by_train_number(driver, ttn, max_attempts=0, refresh_interval=(2,4), 
                                           params=params, start_time=start_time, 
                                           monitor_count_ref={'count': 0}, last_notification_time=last_notification_time)
        else:
            tr = params['depart_time_range']
            logger.info(f"策略：时间范围 [{tr['start']} - {tr['end']}]")
            result_msg = book_by_time_range(driver, tr['start'], tr['end'], max_attempts=30, refresh_interval=(2,4))
        logger.info(result_msg)
        
        # 发送抢票结果通知
        if '成功' in result_msg:
            content = f"## 抢票任务成功\n" \
                     f"> 结果: {result_msg}\n" \
                     f"> 出发站: {params['from_station']}\n" \
                     f"> 到达站: {params['to_station']}\n" \
                     f"> 日期: {params['travel_date']}\n" \
                     f"> 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            send_dingtalk_notification('抢票任务成功', content, params.get('dingtalk_token'))
        else:
            content = f"## 抢票任务结束\n" \
                     f"> 结果: {result_msg}\n" \
                     f"> 出发站: {params['from_station']}\n" \
                     f"> 到达站: {params['to_station']}\n" \
                     f"> 日期: {params['travel_date']}\n" \
                     f"> 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            send_dingtalk_notification('抢票任务结束', content, params.get('dingtalk_token'))
        
        # 选择乘车人
        try:
            passenger_name = params.get('passenger_name', '')
            if passenger_name:
                logger.info(f'尝试选择乘车人：{passenger_name}')
                # 尝试通过姓名查找乘车人
                passengers = driver.find_elements(By.XPATH, "//ul[@id='normal_passenger_id']//li")
                selected = False
                for passenger in passengers:
                    if passenger_name in passenger.text:
                        checkbox = passenger.find_element(By.XPATH, ".//input[@type='checkbox']")
                        if checkbox:
                            checkbox.click()
                            logger.info(f'✓ 已成功选择乘车人：{passenger_name}')
                            selected = True
                            break
                if not selected:
                    # 如果找不到指定姓名的乘车人，选择第一个乘车人
                    logger.warning(f'未找到姓名为 {passenger_name} 的乘车人，尝试选择第一个乘车人')
                    passenger_checkbox = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, 'normalPassenger_0')))
                    passenger_checkbox.click()
                    logger.info('✓ 已成功选择第一个乘车人')
            else:
                # 没有指定乘车人姓名，选择第一个乘车人
                passenger_checkbox = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, 'normalPassenger_0')))
                passenger_checkbox.click()
                logger.info('✓ 已成功选择第一个乘车人')
        except Exception as e:
            logger.error(f'选择乘车人失败：{e}', exc_info=True)
        
        try:
            WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.ID, 'dialog_xsertcj_ok'))).click()
        except Exception as e:
            logger.debug(f'点击确认按钮失败：{e}')
        
        # 订单页票种选择
        try:
            if params['ticket_type'] == 'adult':
                ticket_type_select = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.ID, 'ticketType_1')))
                Select(ticket_type_select).select_by_value('1')
                logger.info('✓ 订单页已选择票种：成人票')
        except Exception as e:
            logger.error(f'订单页选择票种失败：{e}', exc_info=True)
        
        # 提交订单
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, 'submitOrder_id'))).click()
            logger.info('✓ 已成功点击提交订单按钮')
        except Exception as e:
            logger.error(f'点击提交订单按钮失败：{e}', exc_info=True)
        time.sleep(0.4)
        
        # 学生票提示
        if params['ticket_type'] == 'student':
            try:
                WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.ID, 'qd_closeDefaultWarningWindowDialog_id'))).click()
            except Exception as e:
                logger.error(f'点击确认按钮失败：{e}', exc_info=True)
        
        # 选座
        select_seat_fast(driver, preferred_type=params.get('seat_position_preference','first'))
        time.sleep(0.8)
        
        # 最终确认
        try:
            WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, 'qr_submit_id'))).click()
            logger.info('✓ 已提交最终确认')
            logger.info('=' * 60)
            logger.info('🎉 抢票流程完成！请在浏览器中完成支付')
            logger.info('=' * 60)
        except Exception as e:
            logger.error(f'点击确认按钮失败：{e}', exc_info=True)
    
    except Exception as e:
        logger.error(f'抢票过程出现异常: {e}', exc_info=True)
        raise
