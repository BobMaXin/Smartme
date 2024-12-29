import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
from tkcalendar import DateEntry
import threading
import time
import pyttsx3
import bcrypt
import os
from PIL import Image, ImageTk
import pystray
from pystray import Icon, Menu, MenuItem
import sys
import random
import win32com.client
import win32api
import win32con

# 初始化语音引擎
engine = pyttsx3.init()

reminder_event = threading.Event()

# 初始化数据库
def initialize_database():
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()

    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            priority TEXT,
            status TEXT DEFAULT '未完成',
            category TEXT DEFAULT '未分类',
            reminder_time TEXT,
            file_path TEXT,  -- 新增字段：任务关联的文件路径
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 分类表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            priority TEXT,
            status TEXT DEFAULT '未完成',
            category TEXT DEFAULT '未分类',
            reminder_time TEXT,
            file_path TEXT,
            user_id INTEGER,
            reminder_paused BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    # 提醒表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            reminder_time TEXT,
            status TEXT DEFAULT '未提醒',
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')

    # 评论表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 任务共享表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_sharing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            shared_user_id INTEGER,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (shared_user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

# 获取用户的任务
def fetch_tasks(user_id):
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE user_id = ?", (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

# 获取共享任务
def fetch_shared_tasks(user_id):
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.* FROM tasks t
        JOIN task_sharing ts ON t.id = ts.task_id
        WHERE ts.shared_user_id = ?
    """, (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

# 添加任务
def add_task(user_id):
    title = entry_title.get()
    description = entry_description.get()
    due_date = entry_due_date.get()
    priority = entry_priority.get()
    category = entry_category.get()
    reminder_time_date = entry_reminder_date.get()
    reminder_time_time = entry_reminder_time.get()
    reminder_time = f"{reminder_time_date} {reminder_time_time}"
    file_path = entry_file_path.get()  # 获取文件路径

    if not title:
        messagebox.showwarning("输入错误", "任务标题不能为空")
        return

    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title, description, due_date, priority, category, reminder_time, file_path, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (title, description, due_date, priority, category, reminder_time, file_path, user_id))
    conn.commit()
    conn.close()

    messagebox.showinfo("成功", "任务已成功添加！")
    update_task_list(user_id)

# 更新任务列表
def update_task_list(user_id):
    for widget in task_frame.winfo_children():
        widget.destroy()

    tasks = fetch_tasks(user_id)
    shared_tasks = fetch_shared_tasks(user_id)

    # 显示用户自己的任务
    for task in tasks:
        task_label = tk.Label(task_frame, text=f"{task[1]} - {task[2]} - {task[3]} - {task[5]}")
        task_label.pack()

        if task[5] == "未完成":
            mark_button = tk.Button(task_frame, text="标记为完成", command=lambda task_id=task[0]: mark_as_completed(task_id, user_id))
            mark_button.pack()

            # 添加评论按钮
            comment_button = tk.Button(task_frame, text="添加评论", command=lambda task_id=task[0]: add_comment_ui(task_id, user_id))
            comment_button.pack()

            # 查看评论按钮
            view_comments_button = tk.Button(task_frame, text="查看评论", command=lambda task_id=task[0]: view_comments_ui(task_id))
            view_comments_button.pack()

            # 共享任务按钮
            share_button = tk.Button(task_frame, text="共享任务", command=lambda task_id=task[0]: share_task_ui(task_id, user_id))
            share_button.pack()

            # 暂停提醒按钮
            paused = task[10]
            if paused:
                pause_text = "恢复提醒"
            else:
                pause_text = "暂停提醒"
            pause_button = tk.Button(task_frame, text=pause_text,
                                     command=lambda task_id=task[0]: pause_task_reminder(task_id, user_id))
            pause_button.pack()


    # 显示共享的任务
    for task in shared_tasks:
        task_label = tk.Label(task_frame, text=f"[共享] {task[1]} - {task[2]} - {task[3]} - {task[5]}")
        task_label.pack()

        if task[5] == "未完成":
            # 创建按钮的代码
            pause_button = tk.Button(task_frame, text=pause_text,command=lambda task_id=task[0]: pause_task_reminder(task_id, user_id))
            pause_button.pack()

            # 添加评论按钮
            comment_button = tk.Button(task_frame, text="添加评论", command=lambda task_id=task[0]: add_comment_ui(task_id, user_id))
            comment_button.pack()

            # 查看评论按钮
            view_comments_button = tk.Button(task_frame, text="查看评论", command=lambda task_id=task[0]: view_comments_ui(task_id))
            view_comments_button.pack()




# 检查任务提醒
def check_task_reminders(user_id):
    while True:
        # 等待事件被设置或者定时检查
        reminder_event.wait(60)
        reminder_event.clear()
        tasks = fetch_tasks(user_id)
        for task in tasks:
            if task[5] == "未完成":
                paused = task[10]
                due_date = task[3]
                remaining_time = calculate_remaining_time(due_date)
                if remaining_time <= 3600:
                    if paused:
                        if remaining_time <= 600:
                            engine.say(f"任务 {task[1]} 即将到期")
                            engine.runAndWait()
                    else:
                        engine.say(f"任务 {task[1]} 即将到期，请尽快完成！")
                        engine.runAndWait()
                        if task[8]:
                            os.startfile(task[8])
        time.sleep(60)

import logging

# 在函数外配置日志记录基本设置（可以放在更合适的全局配置位置）
logging.basicConfig(filename='app.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def pause_task_reminder(task_id, user_id):
    try:
        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        cursor.execute("SELECT reminder_paused FROM tasks WHERE id =? AND user_id =?", (task_id, user_id))
        result = cursor.fetchone()
        if result:
            current_paused = result[0]
            new_paused = not current_paused
            cursor.execute("UPDATE tasks SET reminder_paused =? WHERE id =? AND user_id =?", (new_paused, task_id, user_id))
            conn.commit()
            if new_paused is False:
                reminder_event.set()
        conn.close()
    except sqlite3.Error as e:
        messagebox.showerror("数据库错误", f"数据库操作出现错误: {str(e)}")
        logging.error(f"数据库操作出现错误，任务ID：{task_id}，用户ID：{user_id}，错误信息：{str(e)}")
    finally:
        update_task_list(user_id)
# 标记任务为完成
def mark_as_completed(task_id, user_id):
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = '已完成' WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    conn.close()
    update_task_list(user_id)

# 登录界面
def login_ui():
    login_frame = tk.Frame(root)
    login_frame.pack()

    tk.Label(login_frame, text="用户名").grid(row=0, column=0)
    entry_username = tk.Entry(login_frame)
    entry_username.grid(row=0, column=1)

    tk.Label(login_frame, text="密码").grid(row=1, column=0)
    entry_password = tk.Entry(login_frame, show="*")
    entry_password.grid(row=1, column=1)

    def login():
        username = entry_username.get()
        password = entry_password.get()
        user_id = login_user(username, password)
        if user_id:
            messagebox.showinfo("登录成功", f"欢迎回来，{username}！")
            login_frame.pack_forget()
            task_management_ui(user_id)

    tk.Button(login_frame, text="登录", command=login).grid(row=2, column=0, columnspan=2)

    def register():
        username = entry_username.get()
        password = entry_password.get()
        register_user(username, password)

    tk.Button(login_frame, text="注册", command=register).grid(row=3, column=0, columnspan=2)

# 注册用户
def register_user(username, password):
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    try:
        hashed_password = hash_password(password)
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        conn.close()
        messagebox.showinfo("注册成功", "用户注册成功！")
    except sqlite3.IntegrityError:
        messagebox.showerror("注册失败", "用户名已存在，请选择其他用户名。")

# 登录用户
def login_user(username, password):
    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    if user and check_password(password, user[1]):
        return user[0]
    else:
        messagebox.showerror("登录失败", "用户名或密码错误。")
        return None

# 任务管理界面
def task_management_ui(user_id):
    global entry_title, entry_description, entry_due_date, entry_priority, entry_category, entry_reminder_date, entry_reminder_time, entry_file_path, task_frame

    # 使用 ttk.Style 美化界面
    style = ttk.Style()
    style.theme_use('clam')  # 使用 clam 主题
    style.configure('TButton', foreground='blue', font=('Helvetica', 12))
    style.configure('TLabel', font=('Helvetica', 12))

    task_management_frame = tk.Frame(root)
    task_management_frame.pack()

    # 任务标题
    tk.Label(task_management_frame, text="任务标题").grid(row=0, column=0)
    entry_title = tk.Entry(task_management_frame)
    entry_title.grid(row=0, column=1)

    # 任务描述
    tk.Label(task_management_frame, text="任务描述").grid(row=1, column=0)
    entry_description = tk.Entry(task_management_frame)
    entry_description.grid(row=1, column=1)

    # 到期时间
    tk.Label(task_management_frame, text="到期时间").grid(row=2, column=0)
    entry_due_date = DateEntry(task_management_frame, date_pattern="yyyy-mm-dd")
    entry_due_date.grid(row=2, column=1)

    # 优先级
    tk.Label(task_management_frame, text="优先级").grid(row=3, column=0)
    entry_priority = ttk.Combobox(task_management_frame, values=["低", "中", "高"])
    entry_priority.grid(row=3, column=1)

    # 分类
    tk.Label(task_management_frame, text="分类").grid(row=4, column=0)
    entry_category = ttk.Combobox(task_management_frame, values=["未分类", "工作", "学习", "生活"])
    entry_category.grid(row=4, column=1)

    # 提醒时间（日期）
    tk.Label(task_management_frame, text="提醒日期").grid(row=5, column=0)
    entry_reminder_date = DateEntry(task_management_frame, date_pattern="yyyy-mm-dd")
    entry_reminder_date.grid(row=5, column=1)

    # 提醒时间（时间）
    tk.Label(task_management_frame, text="提醒时间").grid(row=6, column=0)
    entry_reminder_time = tk.Entry(task_management_frame)
    entry_reminder_time.grid(row=6, column=1)

    # 文件路径
    tk.Label(task_management_frame, text="文件路径").grid(row=7, column=0)
    entry_file_path = tk.Entry(task_management_frame)
    entry_file_path.grid(row=7, column=1)

    # 添加任务按钮
    tk.Button(task_management_frame, text="添加任务", command=lambda: add_task(user_id)).grid(row=8, column=0, columnspan=2)

    # 任务列表框架
    task_frame = tk.Frame(task_management_frame)
    task_frame.grid(row=9, column=0, columnspan=2)

    # 更新任务列表
    update_task_list(user_id)

    # 启动后台线程，检查任务的剩余时间
    threading.Thread(target=check_task_reminders, args=(user_id,), daemon=True).start()



# 计算剩余时间
def calculate_remaining_time(due_date):
    due_date = time.strptime(due_date, "%Y-%m-%d")
    due_date = time.mktime(due_date)
    current_time = time.time()
    return due_date - current_time

# 密码哈希
def hash_password(password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password

# 验证密码
def check_password(input_password, hashed_password):
    return bcrypt.checkpw(input_password.encode('utf-8'), hashed_password)

# 添加评论界面
def add_comment_ui(task_id, user_id):
    comment_window = tk.Toplevel(root)
    comment_window.title("添加评论")

    tk.Label(comment_window, text="评论内容").grid(row=0, column=0)
    entry_comment = tk.Entry(comment_window)
    entry_comment.grid(row=0, column=1)

    def add_comment():
        content = entry_comment.get()
        if not content:
            messagebox.showwarning("输入错误", "评论内容不能为空")
            return

        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO comments (task_id, user_id, content) VALUES (?, ?, ?)", (task_id, user_id, content))
        conn.commit()
        conn.close()

        messagebox.showinfo("成功", "评论已成功添加！")
        comment_window.destroy()

    tk.Button(comment_window, text="添加评论", command=add_comment).grid(row=1, column=0, columnspan=2)

# 查看评论界面
def view_comments_ui(task_id):
    comments_window = tk.Toplevel(root)
    comments_window.title("查看评论")

    conn = sqlite3.connect('assistant.db')
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM comments WHERE task_id = ?", (task_id,))
    comments = cursor.fetchall()
    conn.close()

    for comment in comments:
        tk.Label(comments_window, text=comment[0]).pack()

# 共享任务界面
def share_task_ui(task_id, user_id):
    share_window = tk.Toplevel(root)
    share_window.title("共享任务")

    tk.Label(share_window, text="共享用户名").grid(row=0, column=0)
    entry_shared_username = tk.Entry(share_window)
    entry_shared_username.grid(row=0, column=1)

    def share_task():
        shared_username = entry_shared_username.get()
        if not shared_username:
            messagebox.showwarning("输入错误", "共享用户名不能为空")
            return

        conn = sqlite3.connect('assistant.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (shared_username,))
        shared_user = cursor.fetchone()

        if not shared_user:
            messagebox.showerror("错误", "共享用户不存在")
            conn.close()
            return

        shared_user_id = shared_user[0]
        cursor.execute("INSERT INTO task_sharing (task_id, shared_user_id) VALUES (?, ?)", (task_id, shared_user_id))
        conn.commit()
        conn.close()

        messagebox.showinfo("成功", "任务已成功共享！")
        share_window.destroy()

    tk.Button(share_window, text="共享任务", command=share_task).grid(row=1, column=0, columnspan=2)

def add_to_startup():
    from tkinter import messagebox
    import logging
    logging.info("Starting add_to_startup")
    try:
        app_path = os.path.abspath(sys.argv[0])
        logging.info(f"App path: {app_path}")
        startup_folder = win32api.GetSpecialFolderPath(win32con.CSIDL_STARTUP)
        logging.info(f"Startup folder: {startup_folder}")
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut_path = os.path.join(startup_folder, "Smartme.lnk")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = app_path
        shortcut.WorkingDirectory = os.path.dirname(app_path)
        shortcut.save()
        logging.info("Shortcut created")
        messagebox.showinfo("Success", "Application added to startup")
    except PermissionError:
        logging.error("Permission denied when adding to startup")
        messagebox.showerror("Error", "Permission denied. Please run the application as administrator to add it to startup.")
    except Exception as e:
        logging.error(f"Error adding to startup: {e}")
        messagebox.showerror("Error", f"Error adding to startup: {e}")

# Function to check if the application is in startup
def is_in_startup():
    app_path = os.path.abspath(sys.argv[0])
    startup_folder = win32api.GetSpecialFolderPath(win32con.CSIDL_STARTUP)
    for filename in os.listdir(startup_folder):
        if filename == "Smartme.lnk":
            lnk_path = os.path.join(startup_folder, filename)
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            if shortcut.Targetpath == app_path:
                return True
    return False

# 定义全局变量
icon = None  # 用于系统托盘图标
animation_window = None
idle_time = 0


# 定义最小化到托盘的函数
# 最小化到托盘时调用
def minimize_to_tray():
    #print("最小化到托盘")
    root.withdraw()
    show_tray_icon()
#    show_animation()  # 在最小化时显示动画



# 修改主窗口部分
root = tk.Tk()
root.title("智能助手")
root.protocol("WM_DELETE_WINDOW", minimize_to_tray)  # 关闭窗口时最小化到托盘





def show_tray_icon():
    global icon
    image = Image.open("123.png")  # 替换为你的图标路径
    menu = Menu(
        MenuItem('显示', show_window),
        MenuItem('退出', quit_app)
    )
    icon = pystray.Icon("name", image, "智能助手", menu)
    icon.run()

# 显示主窗口时调用
def show_window(icon, item):
    root.deiconify()
    icon.stop()
    hide_animation()  # 隐藏动画窗口


def quit_app(icon, item):
    icon.stop()
    root.destroy()
    sys.exit()

# 跟踪 idle 时间
def update_idle_time(event=None):
    global idle_time
    idle_time = 0

root.bind("<Any-KeyPress>", update_idle_time)
root.bind("<Motion>", update_idle_time)

def check_idle():
    global idle_time, animation_window
    while True:
        time.sleep(1)
        idle_time += 1
        if idle_time >= 6:
            show_animation()
        if root.winfo_ismapped():
            idle_time = 0

# 启动 idle 检查线程
threading.Thread(target=check_idle, daemon=True).start()








def animate(animation_window):
    label = animation_window.label
    photo_images = animation_window.photo_images
    index = animation_window.index
    label.config(image=photo_images[index])
    animation_window.index = (animation_window.index + 1) % len(animation_window.photo_images)
    animation_window.animate_id = animation_window.after(300, animate, animation_window)

def change_position(animation_window, root):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 40
    window_height = 110
    x = random.randint(0, screen_width - window_width)
    y = random.randint(0, screen_height - window_height)
    animation_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    animation_window.position_id = animation_window.after(3000, change_position, animation_window, root)  # 修改为2000毫秒

def hide_animation_and_show_main():
    global animation_window
    if animation_window and animation_window.winfo_exists():
        animation_window.after_cancel(getattr(animation_window, 'animate_id', None))
        animation_window.after_cancel(getattr(animation_window, 'position_id', None))
        animation_window.withdraw()
    root.deiconify()

def show_animation():
    global animation_window
    if animation_window is None or not animation_window.winfo_exists():
        animation_window = tk.Toplevel(root)
        animation_window.overrideredirect(True)
        animation_window.attributes("-topmost", True)

        # 加载动画图像
        image_paths = [f"D:/myproject/python/personal/animation{i}.png" for i in range(1, 6)]
        images = [Image.open(path) for path in image_paths]
        animation_window.photo_images = [ImageTk.PhotoImage(img) for img in images]
        animation_window.label = tk.Label(animation_window, image=animation_window.photo_images[0])
        animation_window.label.pack()

        animation_window.index = 0

        animate(animation_window)
        change_position(animation_window, root)

        # 设置初始位置
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = 40
        window_height = 110
        x = random.randint(0, screen_width - window_width)
        y = random.randint(0, screen_height - window_height)
        animation_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 绑定点击事件，隐藏动画并显示主窗口
        animation_window.bind("<Button-1>", lambda event: hide_animation_and_show_main())
    else:
        animation_window.deiconify()
        # 取消之前的定时器
        animation_window.after_cancel(getattr(animation_window, 'animate_id', None))
        animation_window.after_cancel(getattr(animation_window, 'position_id', None))
        # 重新启动动画和位置变化
        animate(animation_window)
        change_position(animation_window, root)


# 隐藏动画窗口
def hide_animation():
    global animation_window
    if animation_window:
        animation_window.withdraw()



# 在主循环前调用
if __name__ == "__main__":
    # 初始化数据库
    initialize_database()


    # 显示登录界面
    login_ui()
    # 启动主循环
    root.mainloop()