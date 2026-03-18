from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Resident, Household
import json
import subprocess
import os

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
    """Add a new resident."""
    if request.method == 'POST':
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
            occupation=request.POST.get('occupation', ''),
            contact_number=request.POST.get('contact_number', ''),
            email=request.POST.get('email', ''),
            address=request.POST.get('address'),
            purok=request.POST.get('purok', ''),
            is_registered_voter=request.POST.get('is_registered_voter') == 'on',
            is_pwd=request.POST.get('is_pwd') == 'on',
            is_4ps_member=request.POST.get('is_4ps_member') == 'on',
            remarks=request.POST.get('remarks', ''),
        )
        if request.FILES.get('photo'):
            resident.photo = request.FILES['photo']

        household_id = request.POST.get('household')
        if household_id:
            resident.household_id = household_id
            resident.is_household_head = request.POST.get('is_household_head') == 'on'

        resident.save()
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
    resident = get_object_or_404(Resident, pk=pk)
    certificates = resident.certificates.all()[:10]
    return render(request, 'residents/view.html', {
        'resident': resident,
        'certificates': certificates,
    })


@login_required
def resident_edit(request, pk):
    """Edit a resident."""
    resident = get_object_or_404(Resident, pk=pk)

    if request.method == 'POST':
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
        resident.occupation = request.POST.get('occupation', '')
        resident.contact_number = request.POST.get('contact_number', '')
        resident.email = request.POST.get('email', '')
        resident.address = request.POST.get('address')
        resident.purok = request.POST.get('purok', '')
        resident.is_registered_voter = request.POST.get('is_registered_voter') == 'on'
        resident.is_pwd = request.POST.get('is_pwd') == 'on'
        resident.is_4ps_member = request.POST.get('is_4ps_member') == 'on'
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
    """Launch local fingerprint service for a resident."""
    resident = get_object_or_404(Resident, pk=pk)
    
    # We launch the service as a separate process
    # It will communicate back via the API
    service_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'zk_service.py')
    
    try:
        # Run it in a new console so the user can see it
        subprocess.Popen([
            'python', 
            service_path, 
            '--resident', str(pk),
            '--url', request.build_absolute_uri('/')[:-1]
        ], creationflags=subprocess.CREATE_NEW_CONSOLE)
        
        messages.info(request, "Fingerprint scanner started. Please check the scanner window.")
    except Exception as e:
        messages.error(request, f"Failed to start scanner: {e}")
        
    return redirect('residents:view', pk=pk)

@login_required
@csrf_exempt
def resident_update_fingerprint(request, pk):
    """Update resident fingerprint template."""
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
def resident_delete(request, pk):
    """Delete (deactivate) a resident."""
    resident = get_object_or_404(Resident, pk=pk)
    if request.method == 'POST':
        resident.is_active = False
        resident.save()
        messages.success(request, f'Resident {resident.full_name} has been deactivated.')
        return redirect('residents:list')
    return render(request, 'residents/confirm_delete.html', {'resident': resident})


@login_required
def household_list(request):
    """List all households."""
    households = Household.objects.all()
    paginator = Paginator(households, 25)
    page = request.GET.get('page')
    households = paginator.get_page(page)
    return render(request, 'residents/household_list.html', {'households': households})


@login_required
def household_add(request):
    """Add a new household."""
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
    """View household details."""
    household = get_object_or_404(Household, pk=pk)
    members = household.members.all()
    return render(request, 'residents/household_view.html', {
        'household': household,
        'members': members,
    })
