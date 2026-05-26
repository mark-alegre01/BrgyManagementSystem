from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import time
import requests
from django.contrib.auth import get_user_model
User = get_user_model()
from .models import Official
from core.models import UserProfile
from residents.models import Resident
from core.utils.biometric_discovery import get_esp32_base_url


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
        officials = officials.filter(position__in=['captain', 'kagawad', 'secretary', 'treasurer', 'sk_chairman', 'sk_kagawad'])
    elif category == 'bhw':
        officials = officials.filter(position='bhw')
    elif category == 'tanod':
        officials = officials.filter(position='tanod')
    elif category == 'staff':
        # Clerk, BNS, Day Care, Lupon, Staff, etc.
        staff_positions = ['nutrition_scholar', 'day_care_worker', 'lupon', 'clerk', 'staff']
        officials = officials.filter(position__in=staff_positions)
    # If category is 'all' or unknown, officials remains the full list of active officials/staff
    
    data = [
        {
            'id': official.id,
            'resident_id': official.resident.id,
            'full_name': official.resident.full_name,
            'position': official.get_position_display(),
            'photo': official.resident.photo.url if official.resident.photo else None,
            'has_fingerprint': bool(official.fingerprint_template and len(official.fingerprint_template) > 10)
        }
        for official in officials
    ]
    
    return JsonResponse({'status': 'success', 'officials': data})

@login_required
def official_capture_fingerprint(request, pk):
    """Start biometric enrollment using ESP32 R307 fingerprint module."""
    official_id = request.GET.get('official_id') or pk
    
    # Enrollment is handled by the external ESP32 R307 fingerprint module.
    return JsonResponse({
        'status': 'success',
        'message': 'Biometric enrollment initiated using the connected ESP32 R307 fingerprint module.',
        'official_id': official_id
    })


@login_required
def biometric_status(request):
    official_id = request.GET.get('official_id')
    profile_id = request.GET.get('profile_id')
    
    has_template = False
    
    if official_id:
        official = Official.objects.filter(pk=official_id).first()
        has_template = bool(official and official.fingerprint_template and len(official.fingerprint_template) > 10)
    elif profile_id:
        profile = UserProfile.objects.filter(pk=profile_id).first()
        has_template = bool(profile and profile.fingerprint_template and len(profile.fingerprint_template) > 10)
    else:
        profile = getattr(request.user, 'profile', None)
        has_template = bool(profile and profile.fingerprint_template and len(profile.fingerprint_template) > 10)

    return JsonResponse({'has_template': has_template})

@csrf_exempt
def esp32_status_proxy(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    
    esp32_base_url = get_esp32_base_url()
    try:
        # Bypassing proxies for local network reliability
        response = requests.get(f"{esp32_base_url}/status", timeout=4, proxies={'http': None, 'https': None})
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            payload = {'status': 'success', 'message': response.text}
        return JsonResponse(payload, status=response.status_code)
    except Exception:
        # Retry with force scan
        esp32_base_url = get_esp32_base_url(force_scan=True)
        try:
            response = requests.get(f"{esp32_base_url}/status", timeout=4, proxies={'http': None, 'https': None})
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                payload = {'status': 'success', 'message': response.text}
            return JsonResponse(payload, status=response.status_code)
        except requests.RequestException as exc:
            if exc.response is not None:
                 try:
                     return JsonResponse(exc.response.json(), status=exc.response.status_code)
                 except Exception:
                     return JsonResponse({'status': 'error', 'message': f'ESP32 Error: {exc.response.text}'}, status=exc.response.status_code)
            return JsonResponse({
                'status': 'error',
                'message': f'ESP32 disconnected or IP changed. Tried: {esp32_base_url}. Error: {str(exc)}'
            }, status=503)
    except Exception as exc:
        return JsonResponse({
            'status': 'error',
            'message': f'ESP32 status proxy error: {str(exc)}'
        }, status=500)

@csrf_exempt
def esp32_start_enrollment_proxy(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    esp32_base_url = get_esp32_base_url()
    slot_id = request.GET.get('id') or request.POST.get('id')
    
    url = f"{esp32_base_url}/start-enrollment"
    if slot_id:
        url += f"?id={slot_id}"
        
    try:
        # Bypassing proxies for local network reliability
        response = requests.post(url, timeout=25, proxies={'http': None, 'https': None})
        try:
            payload = response.json()
        except ValueError:
            payload = {
                'status': 'error',
                'message': response.text or 'Invalid response from ESP32',
            }
        if response.status_code >= 400 and payload.get('status') != 'error':
            payload['status'] = 'error'
        return JsonResponse(payload, status=response.status_code)
    except Exception:
        esp32_base_url = get_esp32_base_url(force_scan=True)
        url = f"{esp32_base_url}/start-enrollment"
        if slot_id:
            url += f"?id={slot_id}"
        try:
            response = requests.post(url, timeout=25, proxies={'http': None, 'https': None})
            try:
                payload = response.json()
            except ValueError:
                payload = {
                    'status': 'error',
                    'message': response.text or 'Invalid response from ESP32',
                }
            if response.status_code >= 400 and payload.get('status') != 'error':
                payload['status'] = 'error'
            return JsonResponse(payload, status=response.status_code)
        except requests.RequestException as exc:
            if exc.response is not None:
                 try:
                     return JsonResponse(exc.response.json(), status=exc.response.status_code)
                 except Exception:
                     return JsonResponse({'status': 'error', 'message': f'ESP32 Error: {exc.response.text}'}, status=exc.response.status_code)
            return JsonResponse({
                'status': 'error',
                'message': f'ESP32 unreachable at {esp32_base_url}. Error: {str(exc)}'
            }, status=503)
    except Exception as exc:
        return JsonResponse({
            'status': 'error',
            'message': f'ESP32 start-enrollment proxy error: {str(exc)}'
        }, status=500)

@csrf_exempt
def esp32_stop_enrollment_proxy(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    esp32_base_url = get_esp32_base_url()
    try:
        response = requests.post(f"{esp32_base_url}/stop-enrollment", timeout=4, proxies={'http': None, 'https': None})
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            payload = {'status': 'success', 'message': response.text}
        return JsonResponse(payload, status=response.status_code)
    except requests.RequestException as exc:
        return JsonResponse({
            'status': 'error',
            'message': f'ESP32 stop-enrollment proxy failed: {str(exc)}'
        }, status=503)
    except Exception as exc:
        return JsonResponse({
            'status': 'error',
            'message': f'ESP32 stop-enrollment proxy error: {str(exc)}'
        }, status=500)

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
def org_chart(request):
    """Display the organizational chart with dynamic data."""
    officials = Official.objects.filter(status='active').select_related('resident', 'user')
    
    # Organize by position
    captain = officials.filter(position='captain').first()
    secretary = officials.filter(position='secretary').first()
    treasurer = officials.filter(position='treasurer').first()
    kagawads = officials.filter(position='kagawad')
    sk_chairman = officials.filter(position='sk_chairman').first()
    
    def format_node(official, type_name):
        if not official: return None
        # Extract initials
        names = official.resident.full_name.split()
        initials = "".join([n[0] for n in names if n][:2]).upper()
        
        return {
            'id': str(official.id),
            'resident_id': str(official.resident.id),
            'name': official.resident.full_name,
            'role': official.get_position_display(),
            'initials': initials,
            'photo': official.resident.photo.url if official.resident.photo else None,
            'email': official.user.email if (official.user and official.user.email) else 'N/A',
            'phone': official.resident.contact_number or 'N/A',
            'type': type_name,
            'children': []
        }

    root = format_node(captain, 'executive')
    if not root:
        root = {
            'id': 'root',
            'name': 'Barangay Office',
            'role': 'Punong Barangay (Vacant)',
            'initials': 'BR',
            'type': 'executive',
            'children': []
        }

    # Admin Staff Group
    admin_group = []
    sec_node = format_node(secretary, 'admin')
    if sec_node: 
        staff = officials.filter(position__in=['clerk', 'staff', 'lupon', 'day_care_worker'])
        sec_node['children'] = [format_node(s, 'staff') for s in staff]
        admin_group.append(sec_node)
        
    tre_node = format_node(treasurer, 'admin')
    if tre_node: 
        finance_staff = officials.filter(position__in=['nutrition_scholar'])
        tre_node['children'] = [format_node(fs, 'staff') for fs in finance_staff]
        admin_group.append(tre_node)
    
    # Council Group
    council_children = [format_node(k, 'council') for k in kagawads]
    
    sk_node = format_node(sk_chairman, 'council')
    if sk_node:
        sk_kagawads = officials.filter(position='sk_kagawad')
        sk_node['children'] = [format_node(skk, 'council') for skk in sk_kagawads]
        council_children.append(sk_node)

    council_node = {
        'id': 'council_group',
        'name': 'Sangguniang Barangay',
        'role': 'Barangay Council',
        'initials': 'SB',
        'type': 'council',
        'children': council_children
    }

    # BHW and Tanods as separate branches or under Captain?
    # Let's add Tanods and BHWs as departments under root for completeness
    security_node = {
        'id': 'security_group',
        'name': 'Public Safety',
        'role': 'Barangay Tanod',
        'initials': 'PS',
        'type': 'staff',
        'children': [format_node(t, 'staff') for t in officials.filter(position='tanod')]
    }
    
    health_node = {
        'id': 'health_group',
        'name': 'Health Services',
        'role': 'BHW Department',
        'initials': 'HS',
        'type': 'staff',
        'children': [format_node(h, 'staff') for h in officials.filter(position='bhw')]
    }

    root['children'] = admin_group + [council_node]
    if security_node['children']: root['children'].append(security_node)
    if health_node['children']: root['children'].append(health_node)
    
    context = {
        'org_data_json': json.dumps(root)
    }
    return render(request, 'officials/org_chart.html', context)


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

            from core.models import Role, UserProfile
            role_obj = Role.objects.filter(name=position).first()

            username = request.POST.get('username')
            password = request.POST.get('password')

            # Handle User Account Creation/Update
            if hasattr(resident, 'user_profile') and resident.user_profile:
                # Update existing user
                user_profile = resident.user_profile
                user = user_profile.user
                
                # Update role
                if role_obj:
                    user.role = role_obj
                
                # Update username if provided
                if username:
                    user.username = username
                
                # Update password if provided
                if password:
                    user.set_password(password)
                
                user.save()
                official.user = user
                official.save()
            else:
                # Create new user if provided
                if username and password:
                    user = User.objects.create_user(
                        username=username,
                        password=password,
                        first_name=resident.first_name,
                        last_name=resident.last_name,
                    )
                    if role_obj:
                        user.role = role_obj
                        user.save()
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
        profile = getattr(r, 'user_profile', None)
        has_account = profile is not None
        residents_data.append({
            'pk': r.pk,
            'name': f"{r.last_name}, {r.first_name}" + (f" {r.middle_name}" if r.middle_name else "") + (f" {r.suffix}" if r.suffix else "") + (f" — {r.purok}" if r.purok else ""),
            'has_account': has_account,
            'username': profile.user.username if has_account else ''
        })

    # Filter positions if type=staff is provided
    add_type = request.GET.get('type')
    positions = Official.POSITION_CHOICES
    
    if add_type == 'staff':
        # Filter for non-council staff positions
        staff_positions = ['tanod', 'bhw', 'nutrition_scholar', 'day_care_worker', 'lupon', 'clerk', 'staff']
        positions = [p for p in positions if p[0] in staff_positions]

    context = {
        'residents_data': residents_data,
        'positions': positions,
        'add_type': add_type,
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
            profile, _ = UserProfile.objects.get_or_create(user=user)
            from core.models import Role
            role_obj = Role.objects.filter(name=invite.position).first()
            if role_obj:
                user.role = role_obj
                user.save()
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


# ============= 3-SCAN BIOMETRIC ENROLLMENT API =============

def _get_effective_fingerprint_max_slots():
    """
    Prefer the ESP32 sensor's reported library size (GET /status → max_fingerprint_slots),
    capped by FINGERPRINT_SENSOR_MAX_SLOTS. If the scanner is offline or has not reported
    capacity yet, use a conservative default (300) so slot IDs stay valid on typical R307
    modules even when settings allow a higher ceiling.
    """
    settings_cap = max(1, int(getattr(settings, 'FINGERPRINT_SENSOR_MAX_SLOTS', 1000)))
    offline_safe_cap = min(settings_cap, 300)
    esp32_base_url = get_esp32_base_url()
    try:
        response = requests.get(
            f'{esp32_base_url}/status',
            timeout=3,
            proxies={'http': None, 'https': None},
        )
        response.raise_for_status()
        data = response.json()
        raw = data.get('max_fingerprint_slots') or data.get('library_capacity')
        if raw is None:
            return offline_safe_cap
        esp_cap = int(raw)
        if esp_cap <= 0:
            return offline_safe_cap
        return max(1, min(settings_cap, esp_cap))
    except Exception:
        return offline_safe_cap


def _allocate_next_fingerprint_slot(capacity):
    """
    Next free AS608/R307 page index in 0 .. capacity-1 (hardware is 0-based).
    Picks the lowest free index. Returns None if the library is full.
    """
    if capacity <= 0:
        return None
    used_ids = set(
        Resident.objects.filter(fingerprint_id__isnull=False).values_list('fingerprint_id', flat=True)
    )
    for page_id in range(capacity):
        if page_id not in used_ids:
            return page_id
    return None


@login_required
def start_multi_scan_enrollment(request, pk):
    """Initialize 3-scan fingerprint enrollment session."""
    official = get_object_or_404(Official, pk=pk)
    resident = official.resident

    capacity = _get_effective_fingerprint_max_slots()
    fid = resident.fingerprint_id
    # R307/AS608 template indices are 0 .. capacity-1
    needs_slot = fid is None or fid < 0 or fid >= capacity
    if needs_slot:
        slot = _allocate_next_fingerprint_slot(capacity)
        if slot is None:
            return JsonResponse({'status': 'error', 'message': 'No free fingerprint slots available'}, status=507)
        resident.fingerprint_id = slot
        resident.save(update_fields=['fingerprint_id'])

    # Initialize enrollment session in Django
    if 'biometric_enrollment' not in request.session:
        request.session['biometric_enrollment'] = {}
    
    request.session['biometric_enrollment'][str(official.id)] = {
        'scan_count': 0,
        'scans': [],
        'active': True,
        'slot_id': resident.fingerprint_id
    }
    request.session.modified = True
    
    return JsonResponse({
        'status': 'success',
        'message': 'Multi-scan enrollment started. Please prepare to scan your fingerprint 3 times.',
        'official_id': official.id,
        'slot_id': resident.fingerprint_id,
        'scans_required': 3
    })


@login_required
def get_scan_status(request, pk):
    """Get current scan status and check for completion."""
    official = get_object_or_404(Official, pk=pk)
    
    enrollment_data = request.session.get('biometric_enrollment', {}).get(str(official.id), {})
    current_scan_count = enrollment_data.get('scan_count', 0)
    
    return JsonResponse({
        'status': 'success',
        'official_id': official.id,
        'current_scan': current_scan_count,
        'scans_required': 3,
        'enrollment_complete': current_scan_count >= 3,
        'message': f'Scan {current_scan_count} of 3' if current_scan_count < 3 else 'Enrollment complete'
    })


def _biometric_marker_registered(official):
    """True when resident row marks this official as enrolled (template flag or real template)."""
    tpl = official.fingerprint_template if official else None
    return bool(tpl and len(tpl) > 10)


def _persist_biometric_enrollment_complete(request, official):
    """
    Mark official/resident as enrolled after 3 successful ESP32 scans.
    Clears the in-progress enrollment session for this official.
    """
    if 'biometric_enrollment' in request.session and str(official.id) in request.session['biometric_enrollment']:
        del request.session['biometric_enrollment'][str(official.id)]
        request.session.modified = True
    # Explicitly update the resident record which is the single source of truth
    resident = official.resident
    if resident:
        resident.fingerprint_template = 'REGISTERED_ON_SENSOR'
        # Note: fingerprint_id should have been set during start_multi_scan_enrollment
        resident.save(update_fields=['fingerprint_template'])
        
        # Logging for diagnostics on Orange Pi
        print(f"DEBUG: Biometric persistence complete for Official {official.id} (Resident {resident.id})")
    
    # Still call official.save() to trigger any signals or side effects if needed, 
    # but the template is already safely in the Resident table.
    official.save()


@login_required
def sync_scan_progress(request, pk):
    """Sync scan progress coming from ESP32 into Django session."""
    official = get_object_or_404(Official, pk=pk)

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = {}

    esp_scan = data.get('current_scan')
    try:
        esp_scan = int(esp_scan)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid current_scan'}, status=400)

    if 'biometric_enrollment' not in request.session:
        request.session['biometric_enrollment'] = {}

    enrollment = request.session['biometric_enrollment'].get(str(official.id))
    if enrollment is None:
        return JsonResponse(
            {
                'status': 'error',
                'message': 'No enrollment session. Close the dialog and tap Register again.',
            },
            status=400,
        )

    current = enrollment.get('scan_count', 0)
    registration_complete = False
    # Only move forward
    if esp_scan > current:
        new_count = min(esp_scan, 3)
        request.session['biometric_enrollment'][str(official.id)]['scan_count'] = new_count
        request.session.modified = True
        current = new_count
        if new_count >= 3 and not _biometric_marker_registered(official):
            _persist_biometric_enrollment_complete(request, official)
            registration_complete = True
        elif new_count >= 3:
            registration_complete = True

    return JsonResponse({
        'status': 'success',
        'official_id': official.id,
        'current_scan': current,
        'scans_required': 3,
        'registration_complete': registration_complete,
    })


@login_required
def register_fingerprint_after_scans(request, pk):
    """Register fingerprint template after 3 successful scans."""
    official = get_object_or_404(Official, pk=pk)

    if _biometric_marker_registered(official):
        if 'biometric_enrollment' in request.session and str(official.id) in request.session['biometric_enrollment']:
            del request.session['biometric_enrollment'][str(official.id)]
            request.session.modified = True
        return JsonResponse({
            'status': 'success',
            'message': f'Fingerprint already registered for {official.resident.full_name} (Slot {official.resident.fingerprint_id})',
            'official_id': official.id,
            'slot_id': official.resident.fingerprint_id,
        })

    enrollment_data = request.session.get('biometric_enrollment', {}).get(str(official.id), {})
    scan_count = enrollment_data.get('scan_count', 0)

    if scan_count < 3:
        return JsonResponse({
            'status': 'error',
            'message': f'Not enough scans. Completed: {scan_count}/3'
        }, status=400)

    try:
        _persist_biometric_enrollment_complete(request, official)

        return JsonResponse({
            'status': 'success',
            'message': f'Fingerprint successfully registered for {official.resident.full_name} (Slot {official.resident.fingerprint_id})',
            'official_id': official.id,
            'slot_id': official.resident.fingerprint_id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def remove_fingerprint(request, pk):
    """Remove fingerprint template and clear slot ID from sensor."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
        
    official = get_object_or_404(Official, pk=pk)
    resident = official.resident
    
    # 1. Erase template on R307 (retry — WiFi/serial can miss the first attempt)
    if resident.fingerprint_id is not None:
        esp32_base_url = get_esp32_base_url()
        slot = resident.fingerprint_id
        for attempt in range(3):
            try:
                r = requests.post(
                    f"{esp32_base_url}/delete-fingerprint?id={slot}",
                    timeout=5,
                    proxies={'http': None, 'https': None},
                )
                if r.ok:
                    try:
                        if r.json().get('status') == 'success':
                            break
                    except ValueError:
                        break
            except Exception as e:
                if attempt == 2:
                    print(f"[Biometric] Sensor delete failed for {resident.full_name} page {slot}: {e}")
            time.sleep(0.25)
            
    # 2. Clear Django fields
    official.fingerprint_template = ""
    official.save()
    
    resident.fingerprint_id = None
    resident.fingerprint_template = "" # Clear from resident too if it exists there
    resident.save()
    
    return JsonResponse({
        'status': 'success', 
        'message': f'Fingerprint registration removed for {resident.full_name}'
    })
