from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from .models import Resident, Household, ResidentRegistration, Purok
from django.contrib.auth import get_user_model
User = get_user_model()
from core.models import UserProfile, Role
from officials.models import Official
import json

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

    residents = Resident.objects.filter(is_official=False)

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

    context = {
        'residents': residents,
        'puroks': Purok.objects.all(),
        'query': query,
        'selected_purok': purok,
        'selected_gender': gender,
        'selected_status': status,
    }
    return render(request, 'residents/list.html', context)


def generate_unique_username(first_name, last_name):
    """Generate a unique username based on first and last name."""
    base_username = f"{first_name.lower().replace(' ', '')}.{last_name.lower().replace(' ', '')}"
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    return username


def generate_temp_password(last_name, birthdate):
    """Generate a temporary password."""
    # Brgy + Lastname (first letter capitalized) + birth year
    clean_last_name = last_name.replace(' ', '').capitalize()
    birth_year = birthdate.year if hasattr(birthdate, 'year') else timezone.now().year
    return f"Brgy{clean_last_name}{birth_year}"


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

        # Duplicate Check
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        middle_name = request.POST.get('middle_name', '')
        suffix = request.POST.get('suffix', '')
        birthdate_str = request.POST.get('birthdate')
        
        try:
            birthdate = timezone.datetime.strptime(birthdate_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            birthdate = timezone.now().date()

        if Resident.objects.filter(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            suffix=suffix,
            birthdate=birthdate
        ).exists():
            messages.error(request, f"A resident named {first_name} {last_name} with the same birthdate already exists.")
            return redirect('residents:add')

        try:
            with transaction.atomic():
                resident = Resident(
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    suffix=suffix,
                    birthdate=birthdate,
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
                    purok_id=request.POST.get('purok') or None,
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

                # --- AUTO ACCOUNT CREATION ---
                username = generate_unique_username(first_name, last_name)
                password = generate_temp_password(last_name, birthdate)
                
                # Default role is Resident
                resident_role, _ = Role.objects.get_or_create(name='resident', defaults={'display_name': 'Resident', 'permission_level': 3})
                
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=resident.email,
                    role=resident_role
                )
                
                # Link User to Resident via UserProfile
                UserProfile.objects.create(user=user, resident=resident)

                if is_official and official_position:
                    # Lifecycle: Update User Role to Staff if official
                    try:
                        role_name = official_position if Role.objects.filter(name=official_position).exists() else 'staff'
                        role_obj = Role.objects.filter(name=role_name).first()
                        if role_obj:
                            user.role = role_obj
                            user.save()
                    except Exception:
                        pass

                    Official.objects.update_or_create(
                        resident=resident,
                        defaults={
                            'user': user,
                            'position': official_position,
                            'status': 'active',
                            'term_start': timezone.now().date(),
                        }
                    )

                messages.success(request, f'Resident {resident.full_name} added successfully.')
                messages.info(request, f'An account was created for this resident. Username: {username} | Temporary Password: {password}')
                
                return redirect('residents:view', pk=resident.pk)
        
        except Exception as e:
            messages.error(request, f"Error adding resident: {str(e)}")
            return redirect('residents:add')

    households = Household.objects.all()
    puroks = Purok.objects.all()
    return render(request, 'residents/form.html', {
        'resident': Resident(),
        'households': households,
        'puroks': puroks,
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

        # Duplicate Check (only if name or birthdate changed)
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        middle_name = request.POST.get('middle_name', '')
        suffix = request.POST.get('suffix', '')
        birthdate = request.POST.get('birthdate')
        
        if (resident.first_name != first_name or resident.last_name != last_name or 
            resident.middle_name != middle_name or resident.suffix != suffix or 
            str(resident.birthdate) != birthdate):
            if Resident.objects.filter(
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                suffix=suffix,
                birthdate=birthdate
            ).exclude(pk=resident.pk).exists():
                messages.error(request, f"A resident named {first_name} {last_name} with the same birthdate already exists.")
                return redirect('residents:edit', pk=resident.pk)

        resident.first_name = first_name
        resident.last_name = last_name
        resident.middle_name = middle_name
        resident.suffix = suffix
        resident.birthdate = birthdate
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
        resident.purok_id = request.POST.get('purok') or None
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
            
            # Lifecycle: Link User and position (Model save will handle role sync)
            user = None
            if hasattr(resident, 'user_profile'):
                user = resident.user_profile.user

            if official:
                official.user = user
                official.position = official_position
                official.status = 'active'
                official.save()
            else:
                Official.objects.create(
                    resident=resident,
                    user=user,
                    position=official_position,
                    status='active',
                    term_start=timezone.now().date()
                )
        elif not is_official and hasattr(resident, 'official_record'):
            # If no longer an official, we mark it inactive
            official = resident.official_record
            official.status = 'inactive'
            # We keep the official.user link but the official.save() will now handle 
            # resetting the User.role back to 'resident' automatically.
            official.save()

        messages.success(request, f'Resident {resident.full_name} updated successfully.')
        return redirect('residents:view', pk=resident.pk)

    households = Household.objects.all()
    puroks = Purok.objects.all()
    return render(request, 'residents/form.html', {
        'resident': resident,
        'households': households,
        'puroks': puroks,
        'editing': True,
    })


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@login_required
def resident_capture_fingerprint(request, pk):
    """Begin fingerprint enrollment using ESP32 R307 device."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
    resident = get_object_or_404(Resident, pk=pk)
    
    if not resident.is_official:
        messages.error(request, "Biometric registration is only available for Barangay Officials and Functionaries.")
        return redirect('residents:view', pk=pk)

    messages.info(request, "Fingerprint enrollment started using the connected ESP32 R307 fingerprint module.")
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
                if not resident.is_official:
                    return JsonResponse({'status': 'error', 'message': 'Only officials can register biometrics'}, status=403)
                resident.fingerprint_template = template
                resident.save()
                return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

@login_required
def resident_delete(request, pk):
    """Delete a resident – admin/staff only."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
    resident = get_object_or_404(Resident, pk=pk)
    if request.method == 'POST':
        full_name = resident.full_name
        try:
            resident.delete()
            messages.success(request, f'Resident {full_name} and associated accounts have been permanently deleted.')
        except Exception as e:
            messages.error(request, f'Could not delete resident: {e}')
        return redirect('residents:list')
    return redirect('residents:list')


@login_required
def resident_change_password(request, pk):
    """Change a resident's system password (Account Owner Only)."""
    resident = get_object_or_404(Resident, pk=pk)
    
    # Check if the logged-in user is the resident who owns the account
    if not (hasattr(resident, 'user_profile') and resident.user_profile.user == request.user):
        messages.error(request, "Permission denied. Only the account owner can change their password.")
        return redirect('residents:view', pk=pk)
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        if new_password:
            user = resident.user_profile.user
            user.set_password(new_password)
            user.save()
            messages.success(request, "Your password has been successfully updated.")
        else:
            messages.error(request, "New password is required.")
            
    return redirect('residents:view', pk=pk)


@login_required
def resident_reset_password(request, pk):
    """Reset a resident's password to a generated temporary one (Admin/Official only)."""
    if is_resident_role(request):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('core:dashboard')
        
    resident = get_object_or_404(Resident, pk=pk)
    
    if request.method == 'POST':
        if hasattr(resident, 'user_profile') and resident.user_profile.user:
            user = resident.user_profile.user
            temp_password = generate_temp_password(resident.last_name, resident.birthdate)
            user.set_password(temp_password)
            user.save()
            messages.success(request, f"Password for {resident.full_name} has been reset.")
            messages.info(request, f"New Temporary Password: {temp_password}")
        else:
            messages.error(request, "Failed to reset password. Ensure the resident has an active system account.")
            
    return redirect('residents:view', pk=pk)


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
            purok_id=request.POST.get('purok') or None,
        )
        household.save()
        messages.success(request, f'Household #{household.household_no} added.')
        return redirect('residents:household_list')
    puroks = Purok.objects.all()
    return render(request, 'residents/household_form.html', {'puroks': puroks})


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

            if Resident.objects.filter(
                first_name=registration.first_name,
                last_name=registration.last_name,
                middle_name=registration.middle_name,
                suffix=registration.suffix,
                birthdate=registration.birthdate
            ).exists():
                raise Exception(f"A resident with this name and birthdate already exists.")

            # 2. Create User (ensure role is set)
            resident_role, _ = Role.objects.get_or_create(name='resident', defaults={'display_name': 'Resident', 'permission_level': 3})
            
            user = User(
                username=registration.username,
                first_name=registration.first_name,
                last_name=registration.last_name,
                email=registration.email,
                role=resident_role
            )
            # The password in ResidentRegistration is already hashed during signup
            user.password = registration.password
            user.save()

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
                is_registered_voter=registration.is_registered_voter,
                photo=registration.photo,
            )
            
            # Handle Purok lookup
            if registration.purok:
                purok_obj, _ = Purok.objects.get_or_create(name=registration.purok)
                resident.purok = purok_obj
                resident.save()

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

@login_required
def registration_delete(request, pk):
    """Delete a specific registration."""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    registration = get_object_or_404(ResidentRegistration, pk=pk)
    if request.method == 'POST':
        ref = registration.reference_number
        registration.delete()
        messages.success(request, f"Registration {ref} has been deleted.")
    return redirect('residents:registration_list')

@login_required
def registration_bulk_delete(request):
    """Delete registrations based on status filter."""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ['pending', 'approved', 'rejected']:
            registrations = ResidentRegistration.objects.filter(status=status)
            count = registrations.count()
            registrations.delete()
            messages.success(request, f"Deleted {count} {status} registrations.")
        elif status == 'all':
            count = ResidentRegistration.objects.all().count()
            ResidentRegistration.objects.all().delete()
            messages.success(request, f"Deleted all {count} registrations.")
    return redirect('residents:registration_list')
@login_required
@csrf_exempt
def purok_add_api(request):
    """API to add a new Purok – authorized officials only."""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            if not name:
                return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)
            
            if Purok.objects.filter(name__iexact=name).exists():
                return JsonResponse({'status': 'error', 'message': 'Purok already exists'}, status=400)
            
            purok = Purok.objects.create(name=name)
            return JsonResponse({'status': 'success', 'id': purok.id, 'name': purok.name})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=405)

def get_resident_by_fingerprint(request):
    """Lookup resident name by fingerprint slot ID."""
    fingerprint_id = request.GET.get('id')
    if fingerprint_id is None or fingerprint_id == '':
        return JsonResponse({'status': 'error', 'message': 'Missing ID'}, status=400)

    resident = Resident.objects.filter(fingerprint_id=fingerprint_id).first()
    if resident:
        return JsonResponse({
            'status': 'success',
            'id': fingerprint_id,
            'name': resident.full_name
        })
    return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
