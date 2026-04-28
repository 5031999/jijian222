import time

# ====================== 你的业务函数（各自不同逻辑） ======================
def task1():
    """任务1：自己的逻辑"""
    print("▶ 执行任务1：正在处理数据...")

def task2():
    """任务2：自己的逻辑"""
    print("▶ 执行任务2：正在发送通知...")

def task3():
    """任务3：自己的逻辑"""
    print("▶ 执行任务3：正在生成报表...")


# ====================== 统一总控函数：按步骤顺序执行 ======================
def execute_all_tasks():
    """
    总控函数：
    1. 顺序执行 task1 → task2 → task3
    2. 每个函数执行满 1 分钟
    3. 后台打印日志
    """
    # 按执行顺序放入列表
    task_list = [task1, task2, task3]

    print("===== 开始执行所有任务 =====")

    for i, task in enumerate(task_list, 1):
        task_name = task.__name__
        start_time = time.time()

        print(f"\n【步骤 {i}】开始执行：{task_name}")
        print("----------------------------------------")

        # 执行任务本身
        task()

        # 确保执行满 1 分钟（60秒）
        elapsed = time.time() - start_time
        if elapsed < 60:
            wait = 60 - elapsed
            print(f"⏳ 任务执行完成，等待剩余时间：{wait:.1f} 秒")
            time.sleep(wait)

        # 结束日志
        print(f"✅ {task_name} 执行完成，总耗时：{time.time() - start_time:.1f} 秒")

    print("\n===== ✅ 所有任务全部执行完毕 =====")


# ====================== 调用：只需要执行这一个总函数 ======================
if __name__ == '__main__':
    execute_all_tasks()