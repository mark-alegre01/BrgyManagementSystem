from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import subprocess
import os
import sys
from django.contrib.auth import get_user_model
User = get_user_model()
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
        from django.contrib.auth import get_user_model
        from django.db import transaction
        User = get_user_model()
        
        resident_id = request.POST.get('resident')
        resident = get_object_or_404(Resident, pk=resident_id)
        position = request.POST.get('position')
        
        with transaction.atomic():
            official = Official(
                resident=resident,
                position=position,
                committee=request.POST.get('committee', ''),
                term_start=request.POST.get('term_start'),
                term_end=request.POST.get('term_end') or None,
                salary=request.POST.get('salary', 0) or 0,
                employee_id=request.POST.get('employee_id', ''),
                status='active',
            )
            official.save()

            # Handle User Account Creation/Update
            if hasattr(resident, 'user_profile') and resident.user_profile:
                # Update existing user role
                user_profile = resident.user_profile
                user = user_profile.user
                user.role = position
                user.save()
                official.user = user
                official.save()
            else:
                # Create new user if provided
                username = request.POST.get('username')
                password = request.POST.get('password')
                
                if username and password:
                    user = User.objects.create_user(
                        username=username,
                        password=password,
                        first_name=resident.first_name,
                        last_name=resident.last_name,
                        role=position
                    )
                    from core.models import UserProfile
                    UserProfile.objects.create(user=user, resident=resident)
                    official.user = user
                    official.save()

            messages.success(request, f'{resident.full_name} added as {official.get_position_display()}. Account setup successfully.')
            return redirect('officials:list')

    # Get residents who are not yet officials
    existing_official_ids = Official.objects.values_list('resident_id', flat=True)
    available_residents = Resident.objects.filter(is_active=True).exclude(id__in=existing_official_ids).prefetch_related('user_profile')
    
    # create a dict to easily check in JS if a resident has a user account
    residents_data = []
    for r in available_residents:
        has_account = hasattr(r, 'user_profile') and r.user_profile is not None
        residents_data.append({
            'pk': r.pk,
            'name': f"{r.last_name}, {r.first_name}" + (f" {r.middle_name}" if r.middle_name else "") + (f" {r.suffix}" if r.suffix else "") + (f" — {r.purok}" if r.purok else ""),
            'has_account': has_account
        })

    context = {
        'residents_data': residents_data,
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


# --- Onboarding Flows ---

import string
import random
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from .models import OfficialInvite, OnboardingAuditLog

def log_onboarding(invite, user, action, request):
    ip = request.META.get('REMOTE_ADDR')
    OnboardingAuditLog.objects.create(
        invite=invite,
        actor=user if user.is_authenticated else None,
        action=action,
        ip_address=ip
    )

@login_required
@user_passes_test(is_barangay_admin)
def invite_official(request):
    """Captain or Admin invites an official."""
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        position = request.POST.get('position')
        phone_number = request.POST.get('phone_number')
        
        invite = OfficialInvite.objects.create(
            first_name=first_name,
            last_name=last_name,
            position=position,
            phone_number=phone_number,
            invited_by=request.user
        )
        log_onboarding(invite, request.user, "Created Invite", request)
        
        # In a real app, you would send an email/SMS here.
        # For now, we flash the link to the captain.
        link = request.build_absolute_uri(reverse('officials:onboard_upload_docs', args=[invite.token]))
        messages.success(request, f"Invite created! Share this link with {first_name}: {link}")
        return redirect('officials:onboard_approvals_list')

    return render(request, 'officials/onboarding/invite_form.html', {
        'positions': Official.POSITION_CHOICES
    })


def onboard_upload_docs(request, token):
    """Offical uses the link to upload documents."""
    invite = get_object_or_404(OfficialInvite, token=token)
    
    if invite.status != 'pending_documents':
        messages.error(request, "This invite link is no longer in the document upload stage.")
        return redirect('core:login')

    if request.method == 'POST':
        if 'appointment_letter' in request.FILES:
            invite.appointment_letter = request.FILES['appointment_letter']
        if 'valid_id' in request.FILES:
            invite.valid_id = request.FILES['valid_id']
            
        if invite.appointment_letter and invite.valid_id:
            invite.status = 'pending_approval'
            invite.save()
            log_onboarding(invite, request.user, "Uploaded Documents", request)
            messages.success(request, "Documents uploaded successfully! Waiting for Captain and Secretary approval.")
            return redirect('core:login')
        else:
            messages.error(request, "Please upload BOTH the Appointment Letter and a Valid ID.")
            
    return render(request, 'officials/onboarding/upload_documents.html', {'invite': invite})


@login_required
@user_passes_test(is_barangay_admin)
def onboard_approvals_list(request):
    """Dashboard for Captain and Secretary to approve pending invites."""
    pending_documents = OfficialInvite.objects.filter(status='pending_documents').order_by('-created_at')
    pending_approval = OfficialInvite.objects.filter(status='pending_approval').order_by('-created_at')
    pending_otp = OfficialInvite.objects.filter(status='pending_otp').order_by('-created_at')
    recent_activated = OfficialInvite.objects.filter(status='activated').order_by('-created_at')[:10]
    
    context = {
        'pending_documents': pending_documents,
        'pending_approval': pending_approval,
        'pending_otp': pending_otp,
        'recent_activated': recent_activated
    }
    return render(request, 'officials/onboarding/approvals.html', context)


@login_required
@user_passes_test(is_barangay_admin)
def onboard_approve(request, token):
    """Captain or Secretary records their approval."""
    invite = get_object_or_404(OfficialInvite, token=token)
    if invite.status != 'pending_approval':
        messages.error(request, "Invite is not ready for approval.")
        return redirect('officials:onboard_approvals_list')
        
    role = request.user.profile.role if hasattr(request.user, 'profile') else 'admin'
    
    if role in ('captain', 'admin'):
        invite.captain_approved = True
        log_onboarding(invite, request.user, "Captain Approved", request)
    if role in ('secretary', 'admin'):
        invite.secretary_approved = True
        log_onboarding(invite, request.user, "Secretary Approved", request)
        
    if invite.captain_approved and invite.secretary_approved:
        invite.status = 'pending_otp'
        # Generate OTP
        code = ''.join(random.choices(string.digits, k=6))
        invite.otp_code = code
        invite.otp_expires_at = timezone.now() + timedelta(minutes=10)
        
        # MOCK SMS
        print(f"!!! [MOCK SMS] To: {invite.phone_number} | OTP: {code} !!!")
        messages.success(request, f"Both approved! OTP has been generated for {invite.first_name}. (Check server console for code)")
        log_onboarding(invite, request.user, "Dual Approval Complete - OTP Generated", request)
    else:
        messages.success(request, "Your approval has been recorded in the system.")
        
    invite.save()
    return redirect('officials:onboard_approvals_list')


def onboard_verify_otp(request, token):
    """Official enters OTP to finalize account setup."""
    invite = get_object_or_404(OfficialInvite, token=token)
    
    if invite.status == 'activated':
        messages.info(request, "This account is already activated. Please login.")
        return redirect('core:login')
        
    if invite.status != 'pending_otp':
        messages.error(request, "This invite is not ready for activation.")
        return redirect('core:login')

    if request.method == 'POST':
        otp = request.POST.get('otp')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        username = request.POST.get('username')
        
        if not invite.is_otp_valid(otp):
            messages.error(request, "Invalid or expired OTP.")
        elif password != password_confirm or not password:
            messages.error(request, "Passwords do not match or are empty.")
        elif not username:
             messages.error(request, "Username is required.")
        elif User.objects.filter(username=username).exists():
             messages.error(request, "Username is already taken.")
        else:
            # Final Activation
            # 1. Create User
            user = User.objects.create_user(username=username, password=password)
            user.first_name = invite.first_name
            user.last_name = invite.last_name
            user.save()
            
            # 2. Create UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': invite.position})
            profile.role = invite.position
            profile.save()
            
            # 3. Create dummy Resident if needed because Official requires OneToOne with Resident
            # In real system, maybe they select existing, but here we just stub it:
            resident = Resident.objects.create(
                first_name=invite.first_name,
                last_name=invite.last_name,
                contact_number=invite.phone_number,
                gender='M',  # Defaulting, since invite didn't capture.
                civil_status='Single',
                birthdate=timezone.now().date(),
                is_active=True
            )
            
            # 4. Create Official
            Official.objects.create(
                resident=resident,
                user=user,
                position=invite.position,
                term_start=timezone.now().date(),
                status='active'
            )
            
            # 5. Update Invite
            invite.status = 'activated'
            invite.save()
            log_onboarding(invite, user, "Activated Account via OTP", request)
            
            messages.success(request, "Account activated successfully! You can now log in.")
            return redirect('core:login')
            
    return render(request, 'officials/onboarding/verify_otp.html', {'invite': invite})
