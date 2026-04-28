# 🚀 快速参考

## 任务状态转换

```
待上传 (pending)
   ↓
上传文件 → 待执行 (queued)
   ↓
队列处理 → 处理中 (processing)
   ↓
完成处理 → 已完成 (completed) 或 错误 (error)
```

## API 速查表

| 功能 | 方法 | 端点 | 返回 |
|------|------|------|------|
| 上传文件到队列 | POST | `/api/process_save/` | {task_id} |
| 获取任务状态 | GET | `/api/tasks/<id>/status/` | {status} |
| 获取队列位置 | GET | `/api/tasks/<id>/queue_status/` | {queue_position, queue_total} |
| 获取队列列表 | GET | `/api/queue/list/` | {processing, queued} |
| 获取进度历史 | GET | `/api/tasks/<id>/progress_history/` | {progress_history} |
| 监听实时进度 | GET(SSE) | `/api/process_progress/<id>/` | streaming |

## 前端界面

### 上传页面 (`/upload/?task_id=123`)
- 顶部：选择文件 + 开始处理按钮
- 队列状态：显示排队位置（如果在队列中）
- 处理进度：实时显示正在处理的文件
- 完成列表：显示已处理的文件

### 主页面 (`/`)
- 进行中 tab：显示处理中的任务（最多1个）
- 已完成 tab：显示完成和错误的任务
- 任务列表：每行显示任务ID、名称、状态和操作按钮

## 关键代码片段

### 启动队列处理
```python
# 自动在上传文件时启动
start_queue_processor()
```

### 检查任务是否在队列中
```javascript
// 前端：定时轮询队列状态
updateQueueStatus(taskId)  // 每2秒调用一次
```

### 更新任务状态
```python
task.status = 'queued'  # 刚上传
task.status = 'processing'  # 开始处理
task.status = 'completed'  # 完成
task.save()
```

## 故障排查

### 任务一直显示"待执行"不处理
**原因：** 队列线程没有启动
**解决：** 
1. 检查日志是否有错误
2. 重启Django服务器
3. 手动上传第二个文件，可能会触发队列启动

### 上传后看不到队列状态
**原因：** 浏览器缓存或JavaScript加载失败
**解决：**
1. Ctrl+F5 强制刷新
2. 检查浏览器控制台是否有JS错误
3. 检查网络标签是否正常请求API

### 任务处理失败但没有错误信息
**原因：** 进度保存到数据库时失败
**解决：**
1. 检查数据库连接
2. 查看Django服务器日志
3. 确保TaskFile模型有progress_history字段

## 性能优化建议

| 优化项 | 方案 | 效果 |
|--------|------|------|
| 减少数据库查询 | 缓存queued任务数 | 10倍 |
| 减少前端轮询 | 增加轮询间隔到5秒 | 60%流量减少 |
| 清理临时文件 | 定期删除temp_uploads | 释放磁盘空间 |
| 优化进度保存 | 改用Redis缓存 | 更快的响应 |

## 监控指标

### 后端
- 队列长度：`TaskFile.objects.filter(status='queued').count()`
- 处理时间：比较processing任务的created_at和current_time
- 错误率：`TaskFile.objects.filter(status='error').count() / total_count`

### 前端
- 页面加载时间
- SSE连接质量
- 队列更新延迟

## 未来改进方向

- [ ] 支持优先级队列（VIP任务优先）
- [ ] 支持批量操作（批量上传、批量删除）
- [ ] 添加任务暂停/恢复功能
- [ ] 并行处理多个任务（需要资源管理）
- [ ] 集成Celery做分布式任务队列
- [ ] 添加任务预计完成时间估算
- [ ] 支持任务依赖关系

## 常用命令

```bash
# 清理临时上传的zip文件
find /path/to/D:/2222/temp_uploads -type f -mtime +7 -delete

# 查看队列中的任务
python manage.py shell
> from task.models import TaskFile
> TaskFile.objects.filter(status__in=['queued', 'processing']).values('id', 'task_name', 'status')

# 清空所有队列任务
python manage.py shell
> TaskFile.objects.filter(status='queued').delete()

# 重置错误任务状态为pending
python manage.py shell
> TaskFile.objects.filter(status='error').update(status='pending')
```

## 调试技巧

### 查看队列处理日志
```python
# 在process_task_queue()中添加
print(f"[{datetime.now()}] 队列长度: {TaskFile.objects.filter(status='queued').count()}")
```

### 前端调试
```javascript
// 在浏览器控制台运行
fetch('/api/queue/list/').then(r => r.json()).then(d => console.log(d))
```

### 模拟慢任务
```python
# 在process_task_file()中添加
time.sleep(30)  # 睡眠30秒来测试队列
```

---

**最后更新：** 2026-04-28  
**版本：** 1.0  
**维护者：** 系统管理员
