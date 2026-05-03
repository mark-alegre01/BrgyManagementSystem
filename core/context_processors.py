from .models import UserProfile, Notification


def user_role_context(request):
    """Inject user_role, user_profile, and notification data into every template context."""
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

    pending_count = 0
    if role in ['captain', 'admin', 'secretary', 'treasurer']:
        from residents.models import ResidentRegistration
        pending_count = ResidentRegistration.objects.filter(status='pending').count()

    # Pending certificate requests count (for admin nav badge)
    pending_cert_requests = 0
    if role and role != 'resident':
        from certifications.models import CertificateRequest
        pending_cert_requests = CertificateRequest.objects.filter(status='pending').count()

    # Notifications for the current user
    unread_notifications_count = 0
    recent_notifications = []
    if request.user.is_authenticated:
        unread_notifications_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        recent_notifications = list(
            Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        )

    return {
        'user_role': role,
        'user_profile': profile,
        'pending_registrations_count': pending_count,
        'pending_cert_requests_count': pending_cert_requests,
        'unread_notifications_count': unread_notifications_count,
        'recent_notifications': recent_notifications,
    }
