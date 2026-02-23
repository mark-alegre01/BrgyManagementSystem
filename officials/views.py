from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Official
from residents.models import Resident


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
