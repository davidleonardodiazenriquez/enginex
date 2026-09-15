from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_safe


@login_required
@require_safe
def process_workspace(request):
    return render(request, "core/process.html")
