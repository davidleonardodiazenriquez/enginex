from django.http import JsonResponse


def home(request):
    return JsonResponse({"application": "enginex", "status": "running"})


def health(request):
    return JsonResponse({"status": "healthy"})
