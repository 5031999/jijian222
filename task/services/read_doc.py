import os
import win32com.client

# ===================== 部署时仅修改这两个路径 =====================
# 1. 需读取的doc文件路径
DOC_FILE = r"D:\\1.doc"
# 2. WPS安装路径（新电脑填写本地wps.exe路径，仅占位，核心用COM调用）
WPS_PATH = r"D:\\soft\\WPS Office\\12.1.0.25865\\office6\\wps.exe"
# =================================================================

def read_doc_full(doc_path):
    if not os.path.exists(doc_path):
        return "文件不存在"

    wps = None
    try:
        wps = win32com.client.Dispatch("Kwps.Application")
        wps.Visible = False
        wps.DisplayAlerts = 0

        doc = wps.Documents.Open(os.path.abspath(doc_path))
        full_text = []
        for paragraph in doc.Paragraphs:
            text = paragraph.Range.Text.strip()
            if text:
                full_text.append(text)

        doc.Close()
        return "\n".join(full_text)

    except Exception as e:
        return f"读取失败：{str(e)}"
    finally:
        if wps:
            try:
                wps.Quit()
            except:
                pass

if __name__ == "__main__":
    print("=" * 60)
    print("文档读取结果")
    print("=" * 60)
    print(read_doc_full(DOC_FILE))
    input()