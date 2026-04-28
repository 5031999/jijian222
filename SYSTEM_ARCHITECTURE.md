# 🏗️ 系统架构图

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                       前端 (Browser)                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐         ┌──────────────────┐              │
│  │  index.html  │         │  upload.html     │              │
│  │  (主页面)    │         │  (上传页面)      │              │
│  │              │         │                  │              │
│  │ - 任务列表   │         │ - 文件选择       │              │
│  │ - 状态显示   │         │ - 队列监控       │              │
│  │ - 创建任务   │         │ - 进度显示       │              │
│  └──────────────┘         └──────────────────┘              │
└────────────┬──────────────────────────┬─────────────────────┘
             │                          │
        HTTP/AJAX                   SSE(EventSource)
             │                          │
┌────────────▼──────────────────────────▼─────────────────────┐
│                    后端 (Django)                             │
├──────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐ │
│  │               REST API (urls.py)                       │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ POST   /api/process_save/                              │ │
│  │ GET    /api/process_progress/<id>/        (SSE)        │ │
│  │ GET    /api/tasks/<id>/status/                         │ │
│  │ GET    /api/tasks/<id>/queue_status/                   │ │
│  │ GET    /api/tasks/<id>/progress_history/               │ │
│  │ GET    /api/queue/list/                                │ │
│  │ GET    /api/tasks/<id>/download/                       │ │
│  │ POST   /api/tasks/create/                              │ │
│  │ POST   /api/tasks/<id>/delete/                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                    │
│           ┌──────────────▼───────────────┐                   │
│           │   业务逻辑 (file_handle.py)  │                  │
│           ├───────────────────────────────┤                  │
│           │                               │                  │
│           │  ┌──────────────────────────┐│                  │
│           │  │ 队列管理模块             ││                  │
│           │  ├──────────────────────────┤│                  │
│           │  │- start_queue_processor() ││                  │
│           │  │- process_task_queue()    ││ 后台线程        │
│           │  │- process_task_file()     ││                  │
│           │  │- queue_lock              ││                  │
│           │  │- queue_processing        ││                  │
│           │  └──────────────────────────┘│                  │
│           │                               │                  │
│           │  ┌──────────────────────────┐│                  │
│           │  │ 任务处理模块             ││                  │
│           │  ├──────────────────────────┤│                  │
│           │  │- process_folder_...()    ││                  │
│           │  │- process_document()      ││                  │
│           │  │- jiekou()                ││                  │
│           │  │- TextExtractor           ││                  │
│           │  └──────────────────────────┘│                  │
│           │                               │                  │
│           │  ┌──────────────────────────┐│                  │
│           │  │ 进度管理模块             ││                  │
│           │  ├──────────────────────────┤│                  │
│           │  │- save_progress_to_db()   ││                  │
│           │  │- progress_store{}        ││  内存缓存        │
│           │  └──────────────────────────┘│                  │
│           │                               │                  │
│           └───────────────┬───────────────┘                  │
│                           │                                   │
│       ┌───────────────────┼───────────────────┐              │
│       │                   │                   │              │
│       ▼                   ▼                   ▼              │
│  ┌─────────┐        ┌──────────┐      ┌──────────────┐    │
│  │TaskFile │        │ OCR服务  │      │ 链条处理     │    │
│  │ (ORM)   │        │ 模块     │      │ 模块         │    │
│  └─────────┘        └──────────┘      └──────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   ┌──────────┐  ┌──────────┐   ┌──────────────┐
   │PostgreSQL│  │ 本地文件 │   │  Windows OS  │
   │  数据库  │  │ 系统     │   │  文件系统    │
   └──────────┘  └──────────┘   └──────────────┘
```

## 任务队列状态机

```
┌─────────┐
│ pending │  用户创建任务，等待上传文件
└────┬────┘
     │ 用户上传zip文件
     │ POST /api/process_save/
     ▼
┌─────────┐
│ queued  │  文件已保存到临时目录，等待队列处理
└────┬────┘  显示"⏳ 待执行"
     │ 队列处理线程检测到任务
     │ process_task_queue()
     ▼
┌──────────────┐
│ processing   │  正在执行文件处理、OCR、链条处理
└────┬─────────┘  显示"🔄 处理中" + 实时进度
     │ 处理完成 或 处理失败
     │
     ├─► ┌──────────┐
     │   │completed │  处理完成，显示"✅ 已完成"
     │   └──────────┘
     │
     └─► ┌───────┐
         │ error │  处理失败，显示"❌ 错误"
         └───────┘
```

## 数据流：上传文件

```
用户选择zip文件
    │
    ▼
前端：processSave()
    │ form-data: {zip_file, task_id}
    ▼
POST /api/process_save/
    │
    ▼
后端：process_save()
    ├─ 保存zip到 temp_uploads/task_123_timestamp.zip
    ├─ TaskFile.file_path = zip_path
    ├─ TaskFile.status = 'queued'
    ├─ start_queue_processor()  启动队列线程
    │
    ▼
返回 { code: 0, task_id: 123, msg: "..." }
    │
    ▼
前端：checkTaskStatus(123)
    │ GET /api/tasks/123/status/
    ▼
获得 status: 'queued'
    │
    ▼
startQueueStatusMonitor(123)
    │ 每2秒：GET /api/tasks/123/queue_status/
    ▼
显示 "⏳ 排队位置: 第2个"
```

## 数据流：队列处理

```
process_task_queue() 线程
    │ 每1秒检查一次
    ▼
SELECT TaskFile WHERE status='queued' 
  ORDER BY created_at LIMIT 1
    │
    ├─ 没有queued任务 → sleep(1秒) → 重复
    │
    └─ 找到最早的queued任务
        │
        ▼
    task.status = 'processing'
    task.save()
        │
        ▼
    process_task_file(task, send_progress)
        │
        ├─ 读取zip文件
        ├─ 解压到 D:\2222\timestamp\
        ├─ 递归处理文件夹
        │   ├─ PDF/DOC: OCR提取文本
        │   ├─ 图片: OCR提取文本
        │   └─ 调用 send_progress() 更新进度
        │       ├─ 内存: progress_store[task_id].append()
        │       ├─ 数据库: task.progress_history.append()
        │       └─ SSE: EventSource推送给客户端
        ├─ 执行链条处理 jiekou()
        │
        ▼
    if 成功:
        task.status = 'completed'
    else:
        task.status = 'error'
    task.save()
        │
        ▼
    继续处理下一个queued任务
```

## 前端状态转换

```
页面加载 (/upload/?task_id=123)
    │
    ▼
checkTaskStatus(123)
  GET /api/tasks/123/status/
    │
    ├─ status='pending'
    │   └─ 显示文件上传界面
    │
    ├─ status='queued'
    │   └─ startQueueStatusMonitor()
    │       └─ 每2秒检查队列位置
    │       └─ 显示"⏳ 待执行 - 排队位置: 第2个"
    │
    ├─ status='processing'
    │   ├─ 清除队列监控
    │   ├─ restoreProgressHistory()
    │   │   └─ GET /api/tasks/123/progress_history/
    │   │   └─ 重播历史进度到UI
    │   └─ connectProgressStream(123)
    │       └─ SSE /api/process_progress/123/
    │       └─ 实时显示新进度
    │
    └─ status='completed' / 'error'
        └─ 显示完成或错误信息
```

## 模块依赖关系

```
models.py (TaskFile)
    ▲
    │ 导入
    │
file_handle.py
    │
    ├─→ views.py (duty.py)
    │
    ├─→ services/
    │   ├─ orc_service.py
    │   ├─ ocr_trans.py
    │   └─ read_doc.py
    │
    └─→ model_handles.py (duiji11111)

urls.py
    │
    └─→ file_handle.py (所有API视图)

templates/
    ├─ index.html
    │   └─ 调用 /api/tasks/*
    │
    └─ upload.html
        └─ 调用 /api/process_save/
           └─ 调用 /api/process_progress/<id>/
           └─ 调用 /api/tasks/<id>/status/
           └─ 调用 /api/tasks/<id>/queue_status/
```

## 并发控制

```
全局变量保护：

queue_lock (threading.Lock())
    │
    ├─ 保护: queue_processing 标志
    │
    └─ 确保: start_queue_processor() 仅启动一次


progress_store (dict)
    │
    ├─ 每个task_id对应一个列表
    │
    └─ 用途: 临时缓存进度消息，供SSE推送
```

## 性能考虑

```
高频操作 (< 100ms)：
    ├─ GET /api/tasks/<id>/status/          O(1)
    ├─ GET /api/process_progress/<id>/      O(1) 按数组下标
    └─ 内存更新: progress_store.append()    O(1)

中频操作 (< 1s)：
    ├─ GET /api/tasks/<id>/queue_status/    O(n) n=queue长度
    ├─ POST /api/process_save/              O(m) m=文件大小
    └─ save_progress_to_db()                O(1) save

低频操作 (可能 > 10s)：
    ├─ process_task_file()                  O(k) k=文件数量
    ├─ jiekou() 链条处理                    O(p) p=处理复杂度
    └─ GET /api/queue/list/                 O(n)
```

---

这个架构设计的核心特点：
✅ 清晰的分层结构（前端/后端/数据库）
✅ 明确的数据流向
✅ 完整的队列状态机
✅ 并发安全的全局变量保护
✅ 合理的性能考虑
