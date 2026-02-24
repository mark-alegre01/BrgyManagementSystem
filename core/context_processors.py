from .models import UserProfile


def user_role_context(request):
    """Inject user_role and user_profile into every template context."""
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            role = profile.role
        except UserProfile.DoesNotExist:
            profile = None
            role = 'admin' if request.user.is_superuser else 'staff'
    else:
        profile = None
        role = None

    return {
        'user_role': role,
        'user_profile': profile,
    }
