from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from .models import Resident, Household, ResidentRegistration
from django.contrib.auth import get_user_model
User = get_user_model()
from core.models import UserProfile
from officials.models import Official
import json
import subprocess
import os

def is_resident_role(request):
    """Return True if the logged-in user has the 'resident' role."""
    try:
        return request.user.profile.role == 'resident'
    except Exception:
        return False


@login_required
def resident_list(request):
    """List all residents with search and filters."""
    query = request.GET.get('q', '')
    purok = request.GET.get('purok', '')
    gender = request.GET.get('gender', '')
    status = request.GET.get('status', '')

    residents = Resident.objects.all()

    if query:
        residents = residents.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query)
        )
    if purok:
        residents = residents.filter(purok=purok)
    if gender:
        residents = residents.filter(gender=gender)
    if status == 'active':
        residents = residents.filter(is_active=True)
    elif status == 'inactive':
        residents = residents.filter(is_active=False)

    paginator = Paginator(residents, 25)
    page = request.GET.get('page')
    residents = paginator.get_page(page)

    puroks = Resident.objects.values_list('purok', flat=True).distinct().order_by('purok')

    context = {
        'residents': residents,
        'puroks': puroks,
        'query': query,
        'selected_purok': purok,
        'selected_gender': gender,
        'selected_status': status,
    }
    return render(request, 'residents/list.html', context)


@login_required
def resident_add(request):
    """Add a new resident – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
    if request.method == 'POST':
        is_official = request.POST.get('is_official') == 'on'
        occupation = request.POST.get('occupation', '')
        official_position = request.POST.get('official_position', '')

        resident = Resident(
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            middle_name=request.POST.get('middle_name', ''),
            suffix=request.POST.get('suffix', ''),
            birthdate=request.POST.get('birthdate'),
            birthplace=request.POST.get('birthplace', ''),
            gender=request.POST.get('gender'),
            civil_status=request.POST.get('civil_status'),
            nationality=request.POST.get('nationality', 'Filipino'),
            religion=request.POST.get('religion', ''),
            occupation=occupation if not is_official else '',
            is_official=is_official,
            contact_number=request.POST.get('contact_number', ''),
            email=request.POST.get('email', ''),
            address=request.POST.get('address'),
            purok=request.POST.get('purok', ''),
            is_registered_voter=request.POST.get('is_registered_voter') == 'on',
            is_pwd=request.POST.get('is_pwd') == 'on',
            is_4ps_member=request.POST.get('is_4ps_member') == 'on',
            is_senior_citizen=request.POST.get('is_senior_citizen') == 'on',
            remarks=request.POST.get('remarks', ''),
        )
        if request.FILES.get('photo'):
            resident.photo = request.FILES['photo']

        household_id = request.POST.get('household')
        if household_id:
            resident.household_id = household_id
            resident.is_household_head = request.POST.get('is_household_head') == 'on'

        resident.save()

        if is_official and official_position:
            Official.objects.update_or_create(
                resident=resident,
                defaults={
                    'position': official_position,
                    'status': 'active',
                    'term_start': timezone.now().date(),
                }
            )

        messages.success(request, f'Resident {resident.full_name} added successfully.')
        return redirect('residents:view', pk=resident.pk)

    households = Household.objects.all()
    return render(request, 'residents/form.html', {
        'resident': Resident(),
        'households': households,
    })


@login_required
def resident_view(request, pk):
    """View resident details."""
    # Residents may only view their own record
    if is_resident_role(request):
        try:
            own_pk = request.user.profile.resident.pk
        except Exception:
            own_pk = None
        if own_pk is None or pk != own_pk:
            messages.error(request, "You can only view your own profile.")
            return redirect('core:dashboard')
    resident = get_object_or_404(Resident, pk=pk)
    certificates = resident.certificates.all()[:10]
    return render(request, 'residents/view.html', {
        'resident': resident,
        'certificates': certificates,
    })


@login_required
def resident_edit(request, pk):
    """Edit a resident – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
    resident = get_object_or_404(Resident, pk=pk)

    if request.method == 'POST':
        is_official = request.POST.get('is_official') == 'on'
        occupation = request.POST.get('occupation', '')
        official_position = request.POST.get('official_position', '')

        resident.first_name = request.POST.get('first_name')
        resident.last_name = request.POST.get('last_name')
        resident.middle_name = request.POST.get('middle_name', '')
        resident.suffix = request.POST.get('suffix', '')
        resident.birthdate = request.POST.get('birthdate')
        resident.birthplace = request.POST.get('birthplace', '')
        resident.gender = request.POST.get('gender')
        resident.civil_status = request.POST.get('civil_status')
        resident.nationality = request.POST.get('nationality', 'Filipino')
        resident.religion = request.POST.get('religion', '')
        resident.occupation = occupation if not is_official else ''
        resident.is_official = is_official
        resident.contact_number = request.POST.get('contact_number', '')
        resident.email = request.POST.get('email', '')
        resident.address = request.POST.get('address')
        resident.purok = request.POST.get('purok', '')
        resident.is_registered_voter = request.POST.get('is_registered_voter') == 'on'
        resident.is_pwd = request.POST.get('is_pwd') == 'on'
        resident.is_4ps_member = request.POST.get('is_4ps_member') == 'on'
        resident.is_senior_citizen = request.POST.get('is_senior_citizen') == 'on'
        resident.remarks = request.POST.get('remarks', '')

        if request.FILES.get('photo'):
            resident.photo = request.FILES['photo']

        household_id = request.POST.get('household')
        if household_id:
            resident.household_id = household_id
            resident.is_household_head = request.POST.get('is_household_head') == 'on'
        else:
            resident.household = None
            resident.is_household_head = False

        resident.save()

        if is_official and official_position:
            # Check if an official record already exists for this resident
            official = Official.objects.filter(resident=resident).first()
            if official:
                official.position = official_position
                official.status = 'active'
                official.save()
            else:
                Official.objects.create(
                    resident=resident,
                    position=official_position,
                    status='active',
                    term_start=timezone.now().date()
                )
        elif not is_official and hasattr(resident, 'official_record'):
            # If no longer an official, we mark it inactive (or you can delete)
            official = resident.official_record
            official.status = 'inactive'
            official.save()

        messages.success(request, f'Resident {resident.full_name} updated successfully.')
        return redirect('residents:view', pk=resident.pk)

    households = Household.objects.all()
    return render(request, 'residents/form.html', {
        'resident': resident,
        'households': households,
        'editing': True,
    })


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@login_required
def resident_capture_fingerprint(request, pk):
    """Launch local fingerprint service – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
    resident = get_object_or_404(Resident, pk=pk)
    
    # Identify paths
    project_root = os.path.dirname(os.path.dirname(__file__))
    core_dir = os.path.join(project_root, 'core')
    service_path = os.path.join(core_dir, 'zk_service.py')
    venv_python = os.path.join(project_root, 'venv', 'bin', 'python')
    
    # Environment for subprocess
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = f"{core_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    
    try:
        # Log path
        log_path = '/tmp/zk_service.log'
        
        # Launch service
        cmd = [
            venv_python, 
            service_path, 
            '--resident', str(pk),
            '--url', request.build_absolute_uri('/')[:-1]
        ]
        
        # Redirect output to file
        with open(log_path, 'w') as log_file:
            subprocess.Popen(cmd, env=env, stdout=log_file, stderr=log_file)
        
        messages.info(request, f"Fingerprint scanner started. Logging to {log_path}")
    except Exception as e:
        messages.error(request, f"Failed to start scanner: {e}")
        
    return redirect('residents:view', pk=pk)

@login_required
@csrf_exempt
def resident_update_fingerprint(request, pk):
    """Update resident fingerprint – admin/staff only."""
    if is_resident_role(request):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    resident = get_object_or_404(Resident, pk=pk)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            template = data.get('template')
            if template:
                resident.fingerprint_template = template
                resident.save()
                return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

@login_required
@transaction.atomic
def resident_delete(request, pk):
    """Delete a resident – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
    resident = get_object_or_404(Resident, pk=pk)
    if request.method == 'POST':
        full_name = resident.full_name
        
        # Delete associated User account if it exists
        try:
            if hasattr(resident, 'user_profile'):
                user = resident.user_profile.user
                user.delete()
        except Exception:
            pass
            
        resident.delete()
        messages.success(request, f'Resident {full_name} and associated accounts have been permanently deleted.')
        return redirect('residents:list')
    
    # If not POST, just redirect back to list
    return redirect('residents:list')


@login_required
def household_list(request):
    """List all households – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to access this area.")
        return redirect('core:dashboard')
    households = Household.objects.all()
    paginator = Paginator(households, 25)
    page = request.GET.get('page')
    households = paginator.get_page(page)
    return render(request, 'residents/household_list.html', {'households': households})


@login_required
def household_add(request):
    """Add a new household – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
    if request.method == 'POST':
        household = Household(
            household_no=request.POST.get('household_no'),
            address=request.POST.get('address'),
            purok=request.POST.get('purok', ''),
        )
        household.save()
        messages.success(request, f'Household #{household.household_no} added.')
        return redirect('residents:household_list')
    return render(request, 'residents/household_form.html')


@login_required
def household_view(request, pk):
    """View household details – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to access this area.")
        return redirect('core:dashboard')
    household = get_object_or_404(Household, pk=pk)
    members = household.members.all().distinct()
    return render(request, 'residents/household_view.html', {
        'household': household,
        'members': members,
    })

@login_required
def registration_list(request):
    """List pending registrations for officials."""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    registrations = ResidentRegistration.objects.all().order_by('-created_at')
    status_filter = request.GET.get('status', 'pending')
    if status_filter:
        registrations = registrations.filter(status=status_filter)
        
    paginator = Paginator(registrations, 25)
    page = request.GET.get('page')
    registrations = paginator.get_page(page)
    
    return render(request, 'residents/registration_list.html', {
        'registrations': registrations,
        'status_filter': status_filter
    })

@login_required
def registration_detail(request, pk):
    """Review a specific registration."""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
        
    registration = get_object_or_404(ResidentRegistration, pk=pk)
    return render(request, 'residents/registration_detail.html', {
        'registration': registration
    })

@login_required
def approve_registration(request, pk):
    """Approve a registration and create Resident/User/Profile."""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])):
        messages.error(request, "Permission denied.")
        return redirect("core:dashboard")

    if request.method != 'POST':
        messages.error(request, "Invalid request method. Use the approval button.")
        return redirect("residents:registration_detail", pk=pk)

    registration = get_object_or_404(ResidentRegistration, pk=pk)

    if registration.status != "pending":
        messages.error(request, "This registration has already been processed.")
        return redirect("residents:registration_list")

    try:
        with transaction.atomic():
            # 1. Validation Checks (redundant but safe)
            if User.objects.filter(username=registration.username).exists():
                raise Exception(f"Username '{registration.username}' is already taken.")

            if (
                registration.philSys_number
                and UserProfile.objects.filter(philSys_id=registration.philSys_number).exists()
            ):
                raise Exception(f"The PhilSys ID '{registration.philSys_number}' is already registered.")

            # 2. Create User
            user = User.objects.create(
                username=registration.username,
                first_name=registration.first_name,
                last_name=registration.last_name,
                email=registration.email,
                password=registration.password,
            )

            # 3. Create Resident record
            resident = Resident.objects.create(
                first_name=registration.first_name,
                middle_name=registration.middle_name,
                last_name=registration.last_name,
                suffix=registration.suffix,
                birthdate=registration.birthdate,
                birthplace=registration.birthplace,
                gender=registration.gender,
                civil_status=registration.civil_status,
                nationality=registration.nationality,
                religion=registration.religion,
                occupation=registration.occupation,
                contact_number=registration.mobile_number,
                email=registration.email,
                address=", ".join(filter(None, [
                    f"{registration.house_number} {registration.street}".strip(),
                    registration.purok,
                    registration.barangay,
                    registration.municipality,
                    registration.city
                ])),
                purok=registration.purok,
                is_pwd=registration.is_pwd,
                is_senior_citizen=registration.is_senior_citizen,
                is_4ps_member=registration.is_4ps_member,
                is_registered_voter=registration.is_registered_voter,
                photo=registration.photo,
            )

            # Link to household if applicable
            if registration.household_number:
                household = Household.objects.filter(
                    household_no=registration.household_number
                ).first()
                if household:
                    resident.household = household
                    resident.save()

            # 4. Create UserProfile
            UserProfile.objects.create(
                user=user,
                resident=resident,
                role="resident",
            )

            # 5. Update Registration Status
            registration.status = "approved"
            registration.save()

        messages.success(
            request,
            f"Registration approved! User '{registration.username}' and Resident record created.",
        )
        return redirect("residents:registration_list")

    except Exception as e:
        messages.error(request, f"Approval failed: {str(e)}")
        return redirect("residents:registration_detail", pk=pk)

@login_required
def reject_registration(request, pk):
    """Reject a registration."""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
        
    registration = get_object_or_404(ResidentRegistration, pk=pk)
    if request.method == 'POST':
        registration.status = 'rejected'
        registration.save()
        messages.warning(request, f"Registration {registration.reference_number} has been rejected.")
        return redirect('residents:registration_list')
    
    return redirect('residents:registration_detail', pk=pk)
