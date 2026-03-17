#!/usr/bin/env python3
"""
Canvas 签到监控 - 自动按星期选课启动

根据东八区当前星期自动选择对应课程:
  周一 → 中国马克思主义与当代
  周二 → 机器学习理论
  周四 → 强化学习
其他日期无需签到，直接退出。

用法:
  python signin_auto.py              # 自动选课
  python signin_auto.py --test 1     # 测试模式，模拟周一
"""

import sys
import datetime
import os

# 确保脚本目录在 sys.path 中
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from signin_monitor_v3 import SigninMonitorV3

# ── 课程配置 ──────────────────────────────────────────
# 星期 → (课程名, Canvas 签到页 URL)
# 星期编号: 0=周一, 1=周二, ..., 6=周日
COURSE_SCHEDULE = {
    0: ("中国马克思主义与当代", "https://oc.sjtu.edu.cn/courses/90285/external_tools/6650"),
    1: ("机器学习理论", "https://oc.sjtu.edu.cn/courses/91265/external_tools/6650"),
    3: ("强化学习", "https://oc.sjtu.edu.cn/courses/91266/external_tools/6650"),
}

# 检查间隔（秒）
CHECK_INTERVAL = 15


def get_beijing_weekday():
    """获取东八区当前星期几（0=周一）"""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    beijing_now = utc_now.astimezone(beijing_tz)
    return beijing_now.weekday(), beijing_now


def main():
    # 支持 --test N 模拟指定星期
    test_weekday = None
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        if idx + 1 < len(sys.argv):
            # 用户输入 1=周一 ... 7=周日，转为 0-based
            test_weekday = int(sys.argv[idx + 1]) - 1

    if test_weekday is not None:
        weekday = test_weekday
        print(f"[测试模式] 模拟星期{weekday + 1}")
    else:
        weekday, beijing_now = get_beijing_weekday()
        day_names = ["一", "二", "三", "四", "五", "六", "日"]
        print(f"当前北京时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')} 星期{day_names[weekday]}")

    if weekday not in COURSE_SCHEDULE:
        day_names = ["一", "二", "三", "四", "五", "六", "日"]
        print(f"今天是星期{day_names[weekday]}，没有需要签到的课程。")
        sys.exit(0)

    course_name, target_url = COURSE_SCHEDULE[weekday]
    print(f"\n{'='*60}")
    print(f"  今日课程: {course_name}")
    print(f"  签到页面: {target_url}")
    print(f"  检查间隔: {CHECK_INTERVAL}秒")
    print(f"{'='*60}\n")

    monitor = SigninMonitorV3(
        target_url=target_url,
        check_interval=CHECK_INTERVAL,
        feishu_notify=True,
        course_name=course_name,
    )
    monitor.run()


if __name__ == "__main__":
    main()
