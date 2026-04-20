from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import subprocess
import os
import sys
from django.contrib.auth.models import User
from .models import Official
from core.models import UserProfile
from residents.models import Resident


OFFICIAL_USERNAME_BY_ROLE = {
    'captain': 'captain',
    'secretary': 'secretary',
    'treasurer': 'treasurer',
}

from django.contrib.auth.decorators import user_passes_test

def is_barangay_admin(user):
    """Check if user has administrative access (Captain, Secretary, Treasurer, or Admin)."""
    return hasattr(user, 'profile') and user.profile.role in ['captain', 'secretary', 'treasurer', 'admin']

@login_required
@user_passes_test(is_barangay_admin)
def get_officials_by_category(request):
    category = request.GET.get('category', 'all')
    
    officials = Official.objects.filter(status='active').select_related('resident')
    
    if category == 'officials':
        # Punong Barangay, Kagawad, SK Chairman, Secretary, Treasurer
        officials = officials.filter(position__in=['captain', 'kagawad', 'secretary', 'treasurer', 'sk_chairman'])
    elif category == 'bhw':
        officials = officials.filter(position='health_worker')
    elif category == 'tanod':
        officials = officials.filter(position='tanod')
    elif category == 'staff':
        # Clerk, BNS, Day Care, Lupon, Staff
        officials = officials.filter(position__in=['nutrition_scholar', 'day_care_worker', 'lupon', 'clerk', 'staff'])
    
    data = [
        {
            'id': official.id,
            'full_name': official.resident.full_name,
            'position': official.get_position_display(),
            'has_fingerprint': bool(official.fingerprint_template and len(official.fingerprint_template) > 100)
        }
        for official in officials
    ]
    
    return JsonResponse({'status': 'success', 'officials': data})

@login_required
def official_capture_fingerprint(request, pk):
    """Launch local fingerprint service for an official."""
    try:
        # Use target_id from query params if provided (for Official enrollment)
        official_id = request.GET.get('official_id')
        
        target_id = pk
        target_type = '--profile'
        
        if official_id:
            target_id = official_id
            target_type = '--official'
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Use current python executable instead of hardcoded venv32
        venv_python = sys.executable
        service_path = os.path.join(base_dir, 'core', 'zk_service.py')
        
        # Launch the service
        popen_args = [
            venv_python, 
            service_path, 
            target_type, str(target_id),
            '--url', request.build_absolute_uri('/')[:-1]
        ]
        
        if os.name == 'nt':
            subprocess.Popen(popen_args, creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
        else:
            subprocess.Popen(popen_args)
        
        return JsonResponse({'status': 'success', 'message': 'Scanner service launched'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def biometric_status(request):
    official_id = request.GET.get('official_id')
    profile_id = request.GET.get('profile_id')
    
    has_template = False
    
    if official_id:
        official = Official.objects.filter(pk=official_id).first()
        has_template = bool(official and official.fingerprint_template and len(official.fingerprint_template) > 100)
    elif profile_id:
        profile = UserProfile.objects.filter(pk=profile_id).first()
        has_template = bool(profile and profile.fingerprint_template and len(profile.fingerprint_template) > 100)
    else:
        profile = getattr(request.user, 'profile', None)
        has_template = bool(profile and profile.fingerprint_template and len(profile.fingerprint_template) > 100)

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
    """List all officials categorized by position."""
    status_filter = request.GET.get('status', 'active')
    pos_filter = request.GET.get('pos', 'all')
    
    officials = Official.objects.select_related('resident').all()

    if status_filter:
        officials = officials.filter(status=status_filter)
    
    if pos_filter != 'all':
        officials = officials.filter(position=pos_filter)

    # Categories definition
    categories = {
        'council': {
            'title': 'Barangay Council',
            'positions': ['captain', 'kagawad', 'secretary', 'treasurer'],
            'officials': []
        },
        'sk': {
            'title': 'Sangguniang Kabataan (SK)',
            'positions': ['sk_chairman', 'sk_kagawad'],
            'officials': []
        },
        'tanod': {
            'title': 'Barangay Tanod',
            'positions': ['tanod'],
            'officials': []
        },
        'health': {
            'title': 'Health & Nutrition',
            'positions': ['health_worker', 'nutrition_scholar'],
            'officials': []
        },
        'staff': {
            'title': 'Administrative & Support Staff',
            'positions': ['clerk', 'staff', 'day_care_worker', 'lupon'],
            'officials': []
        }
    }

    # Group officials into categories
    for official in officials:
        found = False
        for cat_key, cat_data in categories.items():
            if official.position in cat_data['positions']:
                cat_data['officials'].append(official)
                found = True
                break
        if not found:
            if 'other' not in categories:
                categories['other'] = {'title': 'Other Functionaries', 'officials': []}
            categories['other']['officials'].append(official)

    # Remove empty categories
    active_categories = {k: v for k, v in categories.items() if v['officials']}

    context = {
        'categories': active_categories,
        'selected_status': status_filter,
        'selected_pos': pos_filter,
        'all_positions': Official.POSITION_CHOICES,
    }
    return render(request, 'officials/list.html', context)


@login_required
@user_passes_test(is_barangay_admin)
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
