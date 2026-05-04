from django.http import HttpResponseForbidden
from functools import wraps

def role_required(*allowed_groups):
    """
    Decorator for views that checks whether a user is in the required groups,
    based on the 3 permission levels (admin, staff, resident).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            
            # Allow superusers by default
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Check if user has any of the allowed groups
            user_groups = request.user.groups.values_list('name', flat=True)
            user_groups_set = set(g.lower() for g in user_groups)
            allowed_set = set(a.lower() for a in allowed_groups)
            
            if user_groups_set.intersection(allowed_set):
                return view_func(request, *args, **kwargs)
                
            return HttpResponseForbidden("You do not have permission to access this page.")
        return _wrapped_view
    return decorator
