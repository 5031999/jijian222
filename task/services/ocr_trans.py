import requests
import json
import base64

def image_to_base64(path: str) -> str:
    """
    image 转为 base64格式
    :param path:
    :return:
    """
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def deepseek_ocr_local_file(image_absolute_path: str):
    """
    直接让 Ollama 读取本地图片文件（无需转码，无ollama库）
    :param image_absolute_path: 图片的【绝对路径】
    :return: OCR识别结果
    """
    # Ollama 本地接口
    url = "http://localhost:11434/api/chat"
    
    # 直接传入本地绝对路径，Ollama自动读取文件
    payload = {
        # "model": "deepseek-ocr",
        "model": "qwen3-vl:4b",
        "messages": [
            {
                "role": "user",
                "content": f"识别图片中的所有文字",
                "images": [image_to_base64(image_absolute_path)]  # ✅ 直接传本地路径，模型自己读
            }
        ],
        "stream": False
    }

    # 发送请求
    response = requests.post(
        url=url,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=300
    )

    # 返回结果
    if response.status_code == 200:
        return response.json()["message"]["content"]
    else:
        return f"错误：{response.status_code}，{response.text}"

# ------------------- 测试（替换为你的图片绝对路径） -------------------
if __name__ == "__main__":
    # Windows 绝对路径示例（注意用 / 或者 \\）
    # IMAGE_PATH = "/home/ubuntu/ndt/buhuo.PNG"
    # IMAGE_PATH = "/home/ubuntu/data/1.jpg"
    IMAGE_PATH = "/home/ubuntu/ndt/夏天素材20260417/夏天违纪案件和何慧龙问责案件（案卷扫描版）20260417/何慧龙问责案案卷/证据卷/11-抄送单、相关处分决定、关于夏天同志免职的通知/2026-04-17-19-43-26-01.jpg"
    # Mac/Linux 绝对路径示例
    # IMAGE_PATH = "/Users/你的用户名/Desktop/test.jpg"
    
    result = deepseek_ocr_local_file(IMAGE_PATH)
    print("OCR 识别结果：\n", result)