import time
import re
import platform
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# 飞书通知（可选）
try:
    from feishu_notify import send_feishu_message
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False

class SigninMonitorV3:
    def __init__(self, target_url=None, check_interval=15, feishu_notify=True):
        """
        初始化监控器

        参数:
        - target_url: 目标签到页面URL，默认为None（需要手动指定）
        - check_interval: 检查频率（秒），默认15秒
        - feishu_notify: 是否启用飞书群消息通知，默认True
        """
        self.driver = None
        self.previous_signin_num = None
        self.check_interval = check_interval
        self.attempt_count = 0
        self.feishu_notify = feishu_notify and FEISHU_AVAILABLE

        # 设置目标URL，如果未提供则使用默认值
        if target_url:
            self.target_url = target_url
        else:
            # 默认URL，保持向后兼容
            self.target_url = "https://oc.sjtu.edu.cn/courses/..."

        print(f"🎯 目标URL: {self.target_url}")
        print(f"⏰ 检查频率: {self.check_interval}秒")
        if self.feishu_notify:
            print(f"📨 飞书通知: 已启用")
        elif feishu_notify and not FEISHU_AVAILABLE:
            print(f"⚠️  飞书通知: feishu_notify.py 未找到，已禁用")
        
    def setup_driver(self):
        """设置Chrome驱动"""
        chrome_options = Options()
        
        # 禁用自动化特征检测
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 添加常用参数
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ 浏览器驱动初始化成功")
            return True
        except Exception as e:
            print(f"❌ 驱动初始化失败: {e}")
            return False
    
    def wait_for_manual_login(self):
        """等待用户手动登录"""
        print("\n" + "="*60)
        print("手动登录指引")
        print("="*60)
        print("1. 浏览器将打开上海交通大学Canvas页面")
        print("2. 请完成JAccount登录（用户名、密码、验证码）")
        print("3. 等待页面完全加载，直到看到签到界面")
        print("4. 最后，回到此命令行窗口按回车键继续")
        print("="*60 + "\n")
        
        # 使用配置的目标URL
        print(f"🌐 正在访问: {self.target_url}")
        self.driver.get(self.target_url)
        
        # 等待页面初始加载
        time.sleep(5)
        print("⏳ 页面已加载，请开始登录...")
        
        # 等待用户登录完成
        input("\n✅ 登录完成后，请按回车键继续程序...")
        return True
    
    def find_and_switch_to_signin_iframe(self):
        """查找并切换到签到iframe"""
        print("\n🔍 查找签到iframe...")
        
        # 等待页面完全加载
        time.sleep(5)
        
        # 查找所有iframe
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        print(f"找到 {len(iframes)} 个iframe")
        
        for i, iframe in enumerate(iframes):
            try:
                src = iframe.get_attribute("src") or ""
                print(f"iframe {i+1}: {src[:80]}{'...' if len(src) > 80 else ''}")
                
                # 切换到iframe
                self.driver.switch_to.frame(iframe)
                
                # 检查是否包含签到相关元素
                page_text = self.driver.page_source.lower()
                sign_keywords = ['签到', '签', 'rollcall', 'attendance', '考勤', '点名']
                
                for keyword in sign_keywords:
                    if keyword in page_text:
                        print(f"✅ 已切换到第 {i+1} 个iframe，内容包含签到信息")
                        
                        # 保存iframe内容用于调试
                        with open('iframe_content.html', 'w', encoding='utf-8') as f:
                            f.write(self.driver.page_source[:5000])
                        print("💾 已保存iframe内容到 iframe_content.html")
                        
                        return True
                
                # 没有找到签到信息，切回主文档
                self.driver.switch_to.default_content()
                
            except Exception as e:
                print(f"⚠️  处理iframe {i+1} 失败: {e}")
                try:
                    self.driver.switch_to.default_content()
                except:
                    pass
                continue
        
        print("❌ 未找到包含签到信息的iframe")
        return False
    
    def get_signin_number_from_first_rows(self):
        """从表格中提取签到号。

        Canvas 签到表格结构: 表头行 [签到号, 状态, 创建时间]，
        数据行的第一个 cell 就是签到号（纯数字）。
        改进: 按 cell 精确定位，避免整行正则把日期数字误判为签到号。
        """
        print("\n📊 检查表格中的签到号...")

        try:
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            print(f"找到 {len(tables)} 个表格")

            if not tables:
                print("⚠️  未找到任何表格，尝试其他查找方式...")
                return self.fallback_find_signin_number()

            for table_idx, table in enumerate(tables):
                rows = table.find_elements(By.TAG_NAME, "tr")
                print(f"\n检查表格 {table_idx+1}: {len(rows)} 行")

                if len(rows) < 2:
                    # 至少需要表头+1行数据
                    continue

                # 跳过表头（第0行），从第1行（最新数据）开始
                data_row = rows[1] if len(rows) > 1 else rows[0]
                cells = data_row.find_elements(By.TAG_NAME, "td")

                if not cells:
                    # 有些表格用 div.cell 做单元格（Element UI）
                    cells = data_row.find_elements(By.CSS_SELECTOR, ".cell")

                if cells:
                    first_cell_text = cells[0].text.strip()
                    print(f"  第一个 cell 文本: '{first_cell_text}'")

                    if first_cell_text.isdigit():
                        print(f"  ✅ 签到号: {first_cell_text}")
                        return first_cell_text

                # 如果按 cell 没找到，回退到整行判断
                first_row_text = data_row.text.strip()
                if not first_row_text:
                    continue

                # 只匹配行首独立数字（排除日期中的数字）
                match = re.match(r'^(\d{1,5})\b', first_row_text)
                if match:
                    num = match.group(1)
                    print(f"  ✅ 行首匹配签到号: {num}")
                    return num

                # 整行纯文字，跳过此表格
                print(f"  ⏭️  未找到签到号，跳过此表格")

            print("\n⚠️  所有表格均未找到签到号，尝试备用方式...")
            return self.fallback_find_signin_number()

        except Exception as e:
            print(f"❌ 检查表格时出错: {e}")
            return self.fallback_find_signin_number()
    
    def fallback_find_signin_number(self):
        """备用查找方法"""
        print("\n🔄 使用备用方法查找签到号...")
        
        try:
            # 方法1: 查找所有包含数字的元素
            all_elements = self.driver.find_elements(By.XPATH, "//*[text()]")
            
            candidate_numbers = []
            for elem in all_elements:
                elem_text = elem.text.strip()
                if elem_text and len(elem_text) <= 5:  # 签到号通常不会太长
                    # 检查是否为纯数字
                    if elem_text.isdigit():
                        candidate_numbers.append(elem_text)
            
            if candidate_numbers:
                print(f"📋 找到 {len(candidate_numbers)} 个候选数字")
                # 返回第一个候选数字
                return candidate_numbers[0]
            
            # 方法2: 查找具有特定class的元素
            special_selectors = [
                ".current-row .cell",
                ".el-table__row .cell",
                "[class*='current']",
                "[class*='sign']"
            ]
            
            for selector in special_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        elem_text = elem.text.strip()
                        if elem_text and elem_text.isdigit():
                            print(f"✅ 通过选择器 '{selector}' 找到数字: {elem_text}")
                            return elem_text
                except:
                    continue
            
            print("❌ 备用方法也未找到签到号")
            return None
            
        except Exception as e:
            print(f"❌ 备用查找方法出错: {e}")
            return None
    
    def check_signin_number(self):
        """检查签到号"""
        self.attempt_count += 1
        print(f"\n[{time.strftime('%H:%M:%S')}] 第 {self.attempt_count} 次检查")
        
        try:
            # 刷新页面获取最新数据
            print("🔄 刷新页面...")
            self.driver.refresh()
            time.sleep(5)
            
            # 查找并切换到签到iframe
            if self.find_and_switch_to_signin_iframe():
                # 获取签到号
                current_num = self.get_signin_number_from_first_rows()
                
                if current_num:
                    if self.previous_signin_num is None:
                        print(f"✅ 初始签到号: {current_num}")
                        self.previous_signin_num = current_num
                    elif current_num != self.previous_signin_num:
                        print(f"🚨 签到号已变化!")
                        print(f"   从 {self.previous_signin_num} 变为 {current_num}")
                        self.alert_sound(old_num=self.previous_signin_num, new_num=current_num)
                        self.previous_signin_num = current_num
                    else:
                        print(f"📊 签到号未变: {current_num}")
                else:
                    print("⚠️  未找到签到号")
            else:
                print("❌ 无法访问签到页面")
                
            # 切回主文档，为下次刷新做准备
            self.driver.switch_to.default_content()
            
        except Exception as e:
            print(f"❌ 检查过程中出错: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
    
    def alert_sound(self, old_num=None, new_num=None):
        """发出警报声音 + 飞书群消息通知"""
        # 声音警报
        system = platform.system()
        try:
            if system == "Windows":
                import winsound
                for i in range(5):
                    winsound.Beep(1000 + i*100, 300)
                    time.sleep(0.1)
            elif system == "Darwin":  # macOS
                import os
                os.system('say "签到号变化"')
            elif system == "Linux":
                import os
                for _ in range(3):
                    os.system('echo -e "\a"')
                    time.sleep(0.2)
            else:
                print("\a\a\a")
            print("🔔 签到号变化警报已触发！")
        except Exception as e:
            print(f"⚠️  声音警报失败: {e}")
            print("!" * 50)
            print("!!! 签到号已变化 !!!")
            print("!" * 50)

        # 飞书群消息通知
        if self.feishu_notify:
            try:
                msg = f"[Canvas签到] 签到号变化: {old_num} -> {new_num}"
                send_feishu_message(msg)
                print("📨 飞书通知已发送")
            except Exception as e:
                print(f"⚠️  飞书通知失败: {e}")
    
    def run_monitoring(self):
        """运行监控循环"""
        print("\n🎯 开始监控签到号变化")
        print(f"📈 检查频率: 每{self.check_interval}秒一次")
        print("按下 Ctrl+C 停止监控\n")
        
        # 首次检查
        self.check_signin_number()
        
        try:
            while True:
                # 等待间隔时间
                for remaining in range(self.check_interval, 0, -1):
                    print(f"\r⏳ 下次检查倒计时: {remaining}秒", end='')
                    time.sleep(1)
                print()
                
                # 执行检查
                self.check_signin_number()
                
        except KeyboardInterrupt:
            print("\n\n🛑 监控已停止")
    
    def run(self):
        """运行主程序"""
        print("="*60)
        print("上海交通大学签到号监控系统 V3.1")
        print("="*60)
        
        # 初始化驱动
        if not self.setup_driver():
            return
        
        try:
            # 等待手动登录
            if self.wait_for_manual_login():
                # 开始监控
                self.run_monitoring()
        except Exception as e:
            print(f"❌ 程序运行出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                print("\n🧹 正在清理资源...")
                self.driver.quit()
                print("✅ 浏览器已关闭")
            
            print("\n📊 监控统计:")
            print(f"   检查次数: {self.attempt_count}")
            print(f"   最后签到号: {self.previous_signin_num}")

# 调试函数：详细分析表格结构
def analyze_table_structure(target_url=None, check_interval=15):
    """详细分析页面中的表格结构
    
    参数:
    - target_url: 目标签到页面URL
    - check_interval: 检查频率（秒）
    """
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 使用提供的URL或默认值
    if not target_url:
        target_url = "https://oc.sjtu.edu.cn/courses/..."
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        print(f"🎯 分析目标URL: {target_url}")
        driver.get(target_url)
        
        print("⏳ 请手动登录，然后按回车继续...")
        input()
        
        print("\n🔍 详细分析表格结构...")
        
        # 查找所有iframe
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"找到 {len(iframes)} 个iframe")
        
        for i, iframe in enumerate(iframes):
            src = iframe.get_attribute("src") or ""
            if "mlearning" in src or "rollcall" in src or "lms" in src:
                print(f"\n切换到iframe {i+1}: {src[:80]}...")
                
                driver.switch_to.frame(iframe)
                
                # 查找所有表格
                tables = driver.find_elements(By.TAG_NAME, "table")
                print(f"iframe内找到 {len(tables)} 个表格")
                
                for table_idx, table in enumerate(tables):
                    print(f"\n  表格 {table_idx+1} 分析:")
                    
                    # 获取所有行
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    print(f"    行数: {len(rows)}")
                    
                    # 显示前3行的详细内容
                    for row_idx, row in enumerate(rows[:3]):
                        row_text = row.text.strip()
                        print(f"\n    行 {row_idx+1}:")
                        print(f"      文本: '{row_text}'")
                        
                        # 检查是否为纯数字
                        if row_text.isdigit():
                            print(f"      ✅ 纯数字行!")
                        elif re.search(r'\d', row_text):
                            print(f"      🔢 包含数字: {re.findall(r'\d+', row_text)}")
                        else:
                            print(f"      📝 纯文字行")
                        
                        # 显示HTML片段
                        html_snippet = row.get_attribute('outerHTML')
                        if len(html_snippet) > 200:
                            html_snippet = html_snippet[:200] + "..."
                        print(f"      HTML: {html_snippet}")
                
                driver.switch_to.default_content()
                break  # 只分析第一个包含签到信息的iframe
        
        print("\n✅ 表格结构分析完成")
        
    except Exception as e:
        print(f"分析出错: {e}")
    finally:
        driver.quit()

def print_usage():
    """打印使用说明"""
    print("="*70)
    print("上海交通大学Canvas签到号监控系统 V3.1")
    print("="*70)
    print("\n使用方法:")
    print("1. 正常监控模式:")
    print("   python signin_monitor_v3_1.py [目标URL] [检查间隔]")
    print("   示例: python signin_monitor_v3_1.py https://oc.sjtu.edu.cn/courses/...")
    print()
    print("2. 调试分析模式:")
    print("   python signin_monitor_v3_1.py --analyze [目标URL]")
    print("   示例: python signin_monitor_v3_1.py --analyze https://oc.sjtu.edu.cn/courses/...")
    print()
    print("3. 默认模式（使用默认URL和15秒间隔）:")
    print("   python signin_monitor_v3_1.py")
    print("="*70)

if __name__ == "__main__":
    # 解析命令行参数
    target_url = None
    check_interval = 15
    run_mode = "monitor"  # 默认监控模式
    feishu_enabled = True

    args = sys.argv[1:]

    if "--no-feishu" in args:
        feishu_enabled = False
        args.remove("--no-feishu")

    if args:
        if args[0] == "--analyze":
            run_mode = "analyze"
            if len(args) > 1:
                target_url = args[1]
        elif args[0] in ("--help", "-h"):
            print_usage()
            sys.exit(0)
        else:
            target_url = args[0]
            if len(args) > 1:
                try:
                    check_interval = int(args[1])
                except ValueError:
                    print(f"⚠️  检查间隔参数无效，使用默认值 {check_interval} 秒")

    if run_mode == "analyze":
        analyze_table_structure(target_url, check_interval)
    else:
        if target_url:
            print(f"📋 使用自定义URL: {target_url}")
            print(f"⏰ 检查间隔: {check_interval}秒")

        monitor = SigninMonitorV3(
            target_url=target_url,
            check_interval=check_interval,
            feishu_notify=feishu_enabled,
        )
        monitor.run()