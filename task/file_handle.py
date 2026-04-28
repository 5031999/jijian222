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
from .model_handles import duiji11111

# 全局进度存储
progress_store = {}

BASE_SAVE_DIR = r"D:\2222"


# =========================
# OCR（集成 orc_service 和 ocr_trans）
# =========================
class TextExtractor:
    def __init__(self):
        self.orc_extractor = orc_service.TextExtractor()

    def extract_text(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            # 调用 ocr_trans.py 的方法
            print(f"处理图片文件: {file_path}")
            return ocr_trans.deepseek_ocr_local_file(file_path)
            # return f"处理图片文件: {file_path}"
        elif ext in [".doc", ".docx", ".pdf"]:
            # 调用 orc_service.py 的方法
            return self.orc_extractor.extract_text(file_path)
        else:
            return f"不支持的文件格式: {ext}"


# =========================
# SSE 进度监听接口
# =========================
@csrf_exempt
def process_progress(request, task_id):
    def generate_progress():
        last_progress = []
        while True:
            if task_id in progress_store:
                current_progress = progress_store[task_id]
                new_messages = current_progress[len(last_progress):]
                for message in new_messages:
                    yield f"data: {json.dumps(message)}\n\n"
                last_progress = current_progress.copy()
                if any(msg.get('type') in ['complete', 'error'] for msg in current_progress):
                    break
            time.sleep(1)

    response = StreamingHttpResponse(generate_progress(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Cache-Control'
    return response


# =========================
# ⭐ 核心接口 - 启动后台处理
# =========================
@csrf_exempt
def process_save(request):
    if request.method != "POST":
        return JsonResponse({"code": 1, "msg": "只支持POST"})

    zip_file = request.FILES.get("zip_file")
    task_id = request.POST.get("task_id")

    if not zip_file:
        return JsonResponse({"code": 1, "msg": "没有上传压缩包"})
    if not task_id:
        return JsonResponse({"code": 1, "msg": "缺少task_id"})

    # 初始化进度存储
    progress_store[task_id] = []

    zip_content = b''.join(chunk for chunk in zip_file.chunks())

    def send_progress(message):
        progress_store[task_id].append(message)

    def background_process(zip_data):
        try:
            send_progress({'type': 'start', 'message': '开始处理压缩包...'})

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_root = os.path.join(BASE_SAVE_DIR, timestamp)
            os.makedirs(save_root, exist_ok=True)
            send_progress({'type': 'progress', 'message': f'创建保存目录: {save_root}'})

            zip_path = os.path.join(save_root, "temp.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_data)
            send_progress({'type': 'progress', 'message': '正在解压压缩包...'})

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(save_root)
            os.remove(zip_path)
            send_progress({'type': 'progress', 'message': '解压完成，开始分析文件结构...'})

            extracted_items = os.listdir(save_root)
            if not extracted_items:
                send_progress({'type': 'error', 'message': '压缩包为空'})
                return

            if len(extracted_items) == 1 and os.path.isdir(os.path.join(save_root, extracted_items[0])):
                upload_root = os.path.join(save_root, extracted_items[0])
            else:
                upload_root = save_root

            root_folder = os.path.basename(upload_root)
            send_progress({'type': 'progress', 'message': f'找到根目录: {root_folder}'})

            extractor = TextExtractor()
            send_progress({'type': 'progress', 'message': '开始处理文件...'})

            processed_files = process_folder_with_progress(upload_root, extractor, send_progress, max_workers=1)

            for file_info in processed_files:
                send_progress({'type': 'file_processed', 'file': file_info})
            # =========================
            # 📁 调用下一步对接接口
            # =========================
            send_progress({'type': 'progress', 'message': '所有文件处理完成，开始执行链条处理接口...'})
            jiekou(save_root, task_id, send_progress)
            send_progress({'type': 'complete', 'data': [{'file_name': root_folder, 'save_path': upload_root}]})

        except Exception as e:
            send_progress({'type': 'error', 'message': str(e)})

    thread = threading.Thread(target=background_process, args=(zip_content,))
    thread.daemon = True
    thread.start()

    return JsonResponse({"code": 0, "msg": "处理已启动", "task_id": task_id})


# =========================
# 📁 递归处理目录 - 带进度 & 多线程图片OCR
# =========================
def process_folder_with_progress(current_path, extractor, send_progress, max_workers=8):
    processed_files = []
    image_files = []

    # 遍历当前目录
    for item in os.listdir(current_path):
        full_path = os.path.join(current_path, item)

        if os.path.isdir(full_path):
            sub_processed = process_folder_with_progress(full_path, extractor, send_progress, max_workers)
            processed_files.extend(sub_processed)
            continue

        ext = os.path.splitext(item)[1].lower()

        if ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            image_files.append(full_path)
            processed_files.append({'type': 'image', 'path': full_path, 'status': '待OCR'})
        elif ext in [".doc", ".docx", ".pdf"]:
            # 发送开始处理信号
            send_progress({
                'type': 'file_start',
                'file_type': 'document',
                'file_name': os.path.basename(full_path),
                'file_path': full_path
            })
            process_document(full_path, extractor)
            txt_path = os.path.splitext(full_path)[0] + ".txt"
            # 发送完成处理信号
            send_progress({
                'type': 'file_complete',
                'file_type': 'document',
                'file_name': os.path.basename(full_path),
                'file_path': full_path,
                'output': txt_path
            })
            processed_files.append({'type': 'document', 'path': full_path, 'output': txt_path, 'status': '已提取文本'})

    # 图片 OCR 多线程处理
    if image_files:
        # 去重并按文件名排序
        image_files = sorted(list(set(image_files)), key=lambda x: os.path.basename(x))

        all_text = []

        def ocr_worker(img_path):
            try:
                # 发送开始处理信号
                send_progress({
                    'type': 'file_start',
                    'file_type': 'image',
                    'file_name': os.path.basename(img_path),
                    'file_path': img_path
                })
                
                text = extractor.extract_text(img_path)
                
                # 发送完成处理信号
                send_progress({
                    'type': 'file_complete',
                    'file_type': 'image',
                    'file_name': os.path.basename(img_path),
                    'file_path': img_path
                })
                
                return f"\n===== {os.path.basename(img_path)} =====\n{text}"
            except Exception as e:
                print("OCR失败:", img_path, e)
                # 发送失败信号
                send_progress({
                    'type': 'file_error',
                    'file_type': 'image',
                    'file_name': os.path.basename(img_path),
                    'file_path': img_path,
                    'error': str(e)
                })
                return f"\n===== {os.path.basename(img_path)} =====\n【OCR失败】"

        # ⭐ 使用 executor.map 保证顺序
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(ocr_worker, image_files)
        all_text = list(results)
        txt_path = os.path.join(current_path, "images_ocr.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_text))

        processed_files.append({'type': 'image_ocr', 'path': txt_path, 'status': '图片OCR完成', 'images_count': len(image_files)})

    return processed_files


# =========================
# 📄 文档转 txt
# =========================
def process_document(file_path, extractor):
    try:
        text = extractor.extract_text(file_path)
        txt_path = os.path.splitext(file_path)[0] + ".txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        print("文档处理失败:", file_path, e)



# =========================
# 📁 链条接口
# =========================
def jiekou(save_root, task_id, send_progress):
    """
    链条接口 - 处理已解压和OCR的文件
    :param save_root: 保存的根目录
    :param task_id: 任务ID
    :param send_progress: 进度回调函数
    """
    try:
        send_progress({'type': 'progress', 'message': f'[链条处理] 准备处理任务 {task_id}...'})
        
        task_id_int = int(task_id)
        task = TaskFile.objects.get(id=task_id_int)
        
        send_progress({'type': 'progress', 'message': f'[链条处理] 获取任务信息成功，路径: {save_root}'})

        duiji11111(save_root,task_id,send_progress)
        
        # 更新数据库
        send_progress({'type': 'progress', 'message': '[链条处理] 正在更新数据库...'})
        task.file_path = r"D:\\1.pdf"
        task.status = "completed"
        task.save()
        
        send_progress({'type': 'progress', 'message': '[链条处理] 链条处理完成！数据库已更新'})
        
    except Exception as e:
        send_progress({
            'type': 'error', 
            'message': f'[链条处理] 出错: {str(e)}'
        })
        raise


# =========================
# 📁 重新执行链条接口（不重复OCR）
# =========================
@csrf_exempt
def rejiekou(request, task_id):
    """重新执行 jiekou 方法（无需重复OCR）"""
    if request.method != "POST":
        return JsonResponse({"code": 1, "msg": "只支持POST"})
    
    try:

        # task_id 已从URL参数获取
        if not task_id:
            return JsonResponse({"code": 1, "msg": "缺少task_id"})
        
        task_id_int = int(task_id)
        task = TaskFile.objects.get(id=task_id_int)
        
        # 验证任务状态和文件路径
        if not task.file_path:
            return JsonResponse({"code": 1, "msg": "任务文件路径不存在"})
        
        if not os.path.exists(task.file_path):
            return JsonResponse({"code": 1, "msg": "保存目录已被删除"})
        print("重新执行链条接口，文件路径:", task.file_path)
        #直接执行链条处理
        try:
            #jiekou(task.file_path, task_id)
            return JsonResponse({
                "code": 0, 
                "msg": "链条处理成功",
                "task_id": task_id,
                #"file_path": task.file_path
                "file_path": "1111"
            })
        except Exception as e:
            return JsonResponse({"code": 1, "msg": f"链条处理失败: {str(e)}"})
            
    except Exception as e:
        return JsonResponse({"code": 1, "msg": f"请求处理失败: {str(e)}"})


# =========================
# 📥 文件下载接口
# =========================
@csrf_exempt
def download_file(request, task_id):
    """下载任务相关的文件"""
    try:
        import shutil
        import tempfile
        import mimetypes
        
        task_id_int = int(task_id)
        task = TaskFile.objects.get(id=task_id_int)
        
        if not task.file_path:
            return JsonResponse({"code": 1, "msg": "任务文件路径不存在"})
        
        file_path = task.file_path
        
        # 如果是目录，压缩成ZIP后下载
        if os.path.isdir(file_path):
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()
            zip_file_path = os.path.join(temp_dir, os.path.basename(file_path))
            
            try:
                # 压缩目录
                shutil.make_archive(zip_file_path, 'zip', file_path)
                zip_file_path = zip_file_path + '.zip'
                
                # 文件流生成器
                def file_generator():
                    with open(zip_file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b''):
                            yield chunk
                
                response = StreamingHttpResponse(
                    file_generator(),
                    content_type='application/zip'
                )
                response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}.zip"'
                return response
            except Exception as e:
                raise Exception(f"压缩失败: {str(e)}")
        
        # 如果是文件，直接下载
        elif os.path.isfile(file_path):
            # 获取正确的 MIME 类型
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            
            # 特殊处理 PDF 和 DOCX
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.pdf':
                mime_type = 'application/pdf'
            elif file_ext == '.docx':
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif file_ext == '.doc':
                mime_type = 'application/msword'
            
            # 文件流生成器
            def file_generator():
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        yield chunk
            
            response = StreamingHttpResponse(
                file_generator(),
                content_type=mime_type
            )
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
        
        else:
            return JsonResponse({"code": 1, "msg": "文件不存在"})
        
    except TaskFile.DoesNotExist:
        return JsonResponse({"code": 1, "msg": "任务不存在"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"code": 1, "msg": f"下载失败: {str(e)}"})

