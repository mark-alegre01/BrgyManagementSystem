from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import subprocess
import os
from django.contrib.auth.models import User
from .models import Official
from core.models import UserProfile
from residents.models import Resident


OFFICIAL_USERNAME_BY_ROLE = {
    'captain': 'captain',
    'secretary': 'secretary',
    'treasurer': 'treasurer',
}

@login_required
def official_capture_fingerprint(request, pk):
    """Launch local fingerprint service for an official."""
    try:
        # pk here is a UserProfile PK from the template call, but we may override
        # enrollment target based on selected role.
        role = (request.GET.get('role') or '').strip()
        profile = get_object_or_404(UserProfile, pk=pk)

        if role:
            username = OFFICIAL_USERNAME_BY_ROLE.get(role)
            if not username:
                return JsonResponse({'status': 'error', 'message': 'Invalid role'}, status=400)

            target_user = User.objects.filter(username=username).first()
            if not target_user:
                return JsonResponse({'status': 'error', 'message': f'User for role {role} not found'}, status=404)

            profile, _created = UserProfile.objects.get_or_create(user=target_user, defaults={'role': role})
            if profile.role != role:
                profile.role = role
                profile.save(update_fields=['role'])
        
        # Try to find the Official record associated with this user
        # UserProfile is linked to User.
        # We need to find if there's a Resident or Official related to this user profile.
        # Since 'Resident' model does not have a 'user' field directly (based on the error),
        # we check the Official model which links to Resident.
        
        official = Official.objects.filter(resident__first_name=profile.user.first_name, resident__last_name=profile.user.last_name).first()
        
        resident = None
        if official:
            resident = official.resident
        else:
            # Try to find a resident with matching names if no official record
            resident = Resident.objects.filter(first_name=profile.user.first_name, last_name=profile.user.last_name).first()
        
        # Determine enrollment target
        # Always enroll to UserProfile so biometric login/attendance can work consistently
        target_id = profile.pk
        target_type = '--profile'

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        venv_python = os.path.join(base_dir, 'venv32', 'Scripts', 'python.exe')
        service_path = os.path.join(base_dir, 'core', 'zk_service.py')
        
        if not os.path.exists(venv_python):
            return JsonResponse({'status': 'error', 'message': f'32-bit environment not found at {venv_python}'}, status=500)

        # Launch the 32-bit service in a new console window
        subprocess.Popen([
            venv_python, 
            service_path, 
            target_type, str(target_id),
            '--url', request.build_absolute_uri('/')[:-1]
        ], creationflags=subprocess.CREATE_NEW_CONSOLE)
        
        return JsonResponse({'status': 'success', 'message': 'Scanner service launched'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def biometric_status(request):
    role = (request.GET.get('role') or '').strip()
    profile = None
    if role:
        username = OFFICIAL_USERNAME_BY_ROLE.get(role)
        if username:
            profile = UserProfile.objects.filter(user__username=username).first()
        else:
            profile = UserProfile.objects.filter(role=role).first()
    else:
        profile = getattr(request.user, 'profile', None)

    has_template = bool(profile and getattr(profile, 'fingerprint_template', None))
    return JsonResponse({'has_template': has_template})

@csrf_exempt
def official_update_fingerprint(request, pk):
    """Update official fingerprint template."""
    remote_addr = request.META.get('REMOTE_ADDR')
    if remote_addr not in ('127.0.0.1', '::1'):
        return JsonResponse({'status': 'error', 'message': 'Forbidden'}, status=403)
    official = get_object_or_404(Official, pk=pk)
    if request.method == 'GET':
        return JsonResponse({
            'status': 'ok',
            'message': 'POST fingerprint template to this endpoint.',
            'expected': {'method': 'POST', 'body': {'template': '<base64>'}},
        })

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        template = None

        # Prefer JSON body when available
        if request.body:
            try:
                data = json.loads(request.body)
                template = data.get('template')
            except json.JSONDecodeError:
                template = None

        # Fallback to form POST (application/x-www-form-urlencoded or multipart)
        if not template:
            template = request.POST.get('template')

        if not template:
            return JsonResponse({'status': 'error', 'message': 'Missing template'}, status=400)

        print(f"[Biometric] official_update_fingerprint pk={pk} remote={remote_addr} template_len={len(template)}")
        official.fingerprint_template = template
        official.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
def profile_update_fingerprint(request, pk):
    """Update UserProfile fingerprint template."""
    remote_addr = request.META.get('REMOTE_ADDR')
    if remote_addr not in ('127.0.0.1', '::1'):
        return JsonResponse({'status': 'error', 'message': 'Forbidden'}, status=403)
    profile = get_object_or_404(UserProfile, pk=pk)
    if request.method == 'GET':
        return JsonResponse({
            'status': 'ok',
            'message': 'POST fingerprint template to this endpoint.',
            'expected': {'method': 'POST', 'body': {'template': '<base64>'}},
        })

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        template = None

        # Prefer JSON body when available
        if request.body:
            try:
                data = json.loads(request.body)
                template = data.get('template')
            except json.JSONDecodeError:
                template = None

        # Fallback to form POST (application/x-www-form-urlencoded or multipart)
        if not template:
            template = request.POST.get('template')

        if not template:
            return JsonResponse({'status': 'error', 'message': 'Missing template'}, status=400)

        print(f"[Biometric] profile_update_fingerprint pk={pk} remote={remote_addr} template_len={len(template)}")
        profile.fingerprint_template = template
        profile.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def official_list(request):
    """List all officials."""
    status_filter = request.GET.get('status', 'active')
    officials = Official.objects.select_related('resident').all()

    if status_filter:
        officials = officials.filter(status=status_filter)

    context = {
        'officials': officials,
        'selected_status': status_filter,
    }
    return render(request, 'officials/list.html', context)


@login_required
def biometric_register(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'officials/biometric_register.html', {'profile_pk': profile.pk})


@login_required
def official_add(request):
    """Add a new official."""
    if request.method == 'POST':
        resident_id = request.POST.get('resident')
        resident = get_object_or_404(Resident, pk=resident_id)

        official = Official(
            resident=resident,
            position=request.POST.get('position'),
            committee=request.POST.get('committee', ''),
            term_start=request.POST.get('term_start'),
            term_end=request.POST.get('term_end') or None,
            salary=request.POST.get('salary', 0) or 0,
            employee_id=request.POST.get('employee_id', ''),
            status='active',
        )
        official.save()
        messages.success(request, f'{resident.full_name} added as {official.get_position_display()}.')
        return redirect('officials:list')

    # Get residents who are not yet officials
    existing_official_ids = Official.objects.values_list('resident_id', flat=True)
    available_residents = Resident.objects.filter(is_active=True).exclude(id__in=existing_official_ids)

    context = {
        'residents': available_residents,
        'positions': Official.POSITION_CHOICES,
    }
    return render(request, 'officials/form.html', context)


@login_required
def official_view(request, pk):
    """View official details."""
    official = get_object_or_404(Official.objects.select_related('resident'), pk=pk)
    return render(request, 'officials/view.html', {'official': official})


@login_required
def official_edit(request, pk):
    """Edit an official."""
    official = get_object_or_404(Official, pk=pk)

    if request.method == 'POST':
        official.position = request.POST.get('position')
        official.committee = request.POST.get('committee', '')
        official.term_start = request.POST.get('term_start')
        official.term_end = request.POST.get('term_end') or None
        official.salary = request.POST.get('salary', 0) or 0
        official.employee_id = request.POST.get('employee_id', '')
        official.status = request.POST.get('status', 'active')
        official.save()
        messages.success(request, f'{official.resident.full_name} updated.')
        return redirect('officials:list')

    context = {
        'official': official,
        'editing': True,
        'positions': Official.POSITION_CHOICES,
    }
    return render(request, 'officials/form.html', context)


@login_required
def official_delete(request, pk):
    """Delete an official."""
    official = get_object_or_404(Official, pk=pk)
    if request.method == 'POST':
        official.delete()
        messages.success(request, 'Official record removed.')
        return redirect('officials:list')
    return render(request, 'officials/confirm_delete.html', {'official': official})
