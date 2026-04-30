
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Feedback
from django.shortcuts import redirect


def view_dashboard(request):
    """首页 - 显示view.html (三个功能区)"""
    return render(request, 'view.html')


def index(request):
    """案件分析平台 - 显示index.html (任务管理)"""
    return render(request, 'index.html')


def upload(request):
    task_id = request.GET.get('task_id')
    return render(request, 'upload.html', {'task_id': task_id})





def feedback(request):
    return render(request, 'feedback.html')


def system_intro(request):
    """系统介绍页面 - 显示19_units.html"""
    return render(request, '19_units.html')


def external_link(request):
    """外部链接 - 重定向到百度"""
    return redirect('http://www.baidu.com')

def external_link1(request):
    """外部链接 - 重定向到百度"""
    return redirect('http://www.bing.com')

def external_link2(request):
    """外部链接 - 重定向到百度"""
    return redirect('http://www.google.com')


@csrf_exempt
def submit_feedback(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            content = data.get('content', '')

            if not content:
                return JsonResponse({'success': False, 'message': '内容不能为空'}, status=400)

            Feedback.objects.create(content=content)

            return JsonResponse({'success': True, 'message': '提交成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': '请求方法错误'}, status=405)