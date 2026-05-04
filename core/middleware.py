import time
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

class AutoLogoutMiddleware:
    """
    Auto-logout middleware after 30 minutes of inactivity.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_time = time.time()
            last_activity = request.session.get('last_activity', None)

            if last_activity:
                # Logout if inactive for longer than SESSION_COOKIE_AGE settings
                if (current_time - last_activity) > settings.SESSION_COOKIE_AGE:
                    logout(request)
                    messages.info(request, "Your session has expired due to 30 minutes of inactivity.")
                    return redirect(settings.LOGIN_URL)
            
            # Update the last recorded activity time
            request.session['last_activity'] = current_time

        return self.get_response(request)
