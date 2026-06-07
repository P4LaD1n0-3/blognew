from functools import wraps
from django.shortcuts import redirect


def master_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/painel/login/?next={request.path}')
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect(f'/painel/login/?next={request.path}')
        return view_func(request, *args, **kwargs)
    return wrapper
