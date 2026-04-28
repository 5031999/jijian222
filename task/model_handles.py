import os
import time
import zipfile
import json
import threading
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
from .models import TaskFile
import asyncio
from .services import orc_service, ocr_trans
from concurrent.futures import ThreadPoolExecutor, as_completed


def task3(save_root, task_id, send_progress):
    """任务3：自己的逻辑"""
    time.sleep(5)
    send_progress({
                'type': 'progress', 
                'message': "▶ 执行任务3：正在生成报表..."
            })
    print("▶ 执行任务3：正在生成报表...")



# =========================
# 📁 链条接口
# =========================
def duiji11111(save_root, task_id, send_progress):
    """
    链条接口 - 处理已解压和OCR的文件
    :param save_root: 保存的根目录
    :param task_id: 任务ID
    :param send_progress: 进度回调函数
    """
    try:
        # 循环 10 次，重复发送进度消息
        for i in range(10):
            time.sleep(5)
            send_progress({
                'type': 'progress', 
                'message': f'[链条处理] 准备处理任务 {task_id}... 第 {i+1} 次执行'
            })

            task3(save_root, task_id, send_progress)
        
    except Exception as e:
        send_progress({
            'type': 'error', 
            'message': f'[链条处理] 出错: {str(e)}'
        })
        raise