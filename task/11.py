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

            processed_files = process_folder_with_progress(upload_root, extractor, send_progress, max_workers=8)

            for file_info in processed_files:
                send_progress({'type': 'file_processed', 'file': file_info})

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
            process_document(full_path, extractor)
            txt_path = os.path.splitext(full_path)[0] + ".txt"
            processed_files.append({'type': 'document', 'path': full_path, 'output': txt_path, 'status': '已提取文本'})

    # 图片 OCR 多线程处理
    if image_files:
        # 去重并按文件名排序
        image_files = sorted(list(set(image_files)), key=lambda x: os.path.basename(x))

        all_text = []

        def ocr_worker(img_path):
            try:
                text = extractor.extract_text(img_path)
                send_progress({'type': 'progress', 'message': f'OCR完成: {os.path.basename(img_path)}'})
                return f"\n===== {os.path.basename(img_path)} =====\n{text}"
            except Exception as e:
                print("OCR失败:", img_path, e)
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