from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse
from django.db.models import Q
from .models import Ordinance


@login_required
def ordinance_list(request):
    """List all ordinances with search and filters."""
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    year = request.GET.get('year', '')

    ordinances = Ordinance.objects.all()

    if query:
        ordinances = ordinances.filter(
            Q(title__icontains=query) |
            Q(ordinance_number__icontains=query) |
            Q(author__icontains=query)
        )
    if category:
        ordinances = ordinances.filter(category=category)
    if status:
        ordinances = ordinances.filter(status=status)
    if year:
        ordinances = ordinances.filter(date_enacted__year=year)

    paginator = Paginator(ordinances, 25)
    page = request.GET.get('page')
    ordinances = paginator.get_page(page)

    years = Ordinance.objects.dates('date_enacted', 'year', order='DESC')

    context = {
        'ordinances': ordinances,
        'query': query,
        'selected_category': category,
        'selected_status': status,
        'selected_year': year,
        'categories': Ordinance.CATEGORY_CHOICES,
        'statuses': Ordinance.STATUS_CHOICES,
        'years': years,
    }
    return render(request, 'ordinances/list.html', context)


@login_required
def ordinance_add(request):
    """Add a new ordinance."""
    if request.method == 'POST':
        ordinance = Ordinance(
            ordinance_number=request.POST.get('ordinance_number'),
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            author=request.POST.get('author'),
            date_enacted=request.POST.get('date_enacted'),
            date_effectivity=request.POST.get('date_effectivity') or None,
            category=request.POST.get('category'),
            status=request.POST.get('status', 'active'),
            sponsor=request.POST.get('sponsor', ''),
            remarks=request.POST.get('remarks', ''),
        )
        if request.FILES.get('document_file'):
            ordinance.document_file = request.FILES['document_file']
        ordinance.save()
        messages.success(request, f'Ordinance {ordinance.ordinance_number} added successfully.')
        return redirect('ordinances:view', pk=ordinance.pk)

    return render(request, 'ordinances/form.html', {
        'categories': Ordinance.CATEGORY_CHOICES,
        'statuses': Ordinance.STATUS_CHOICES,
    })


@login_required
def ordinance_view(request, pk):
    """View ordinance details."""
    ordinance = get_object_or_404(Ordinance, pk=pk)
    return render(request, 'ordinances/view.html', {'ordinance': ordinance})


@login_required
def ordinance_edit(request, pk):
    """Edit an ordinance."""
    ordinance = get_object_or_404(Ordinance, pk=pk)

    if request.method == 'POST':
        ordinance.ordinance_number = request.POST.get('ordinance_number')
        ordinance.title = request.POST.get('title')
        ordinance.description = request.POST.get('description', '')
        ordinance.author = request.POST.get('author')
        ordinance.date_enacted = request.POST.get('date_enacted')
        ordinance.date_effectivity = request.POST.get('date_effectivity') or None
        ordinance.category = request.POST.get('category')
        ordinance.status = request.POST.get('status', 'active')
        ordinance.sponsor = request.POST.get('sponsor', '')
        ordinance.remarks = request.POST.get('remarks', '')

        if request.FILES.get('document_file'):
            ordinance.document_file = request.FILES['document_file']

        ordinance.save()
        messages.success(request, f'Ordinance {ordinance.ordinance_number} updated.')
        return redirect('ordinances:view', pk=ordinance.pk)

    return render(request, 'ordinances/form.html', {
        'ordinance': ordinance,
        'editing': True,
        'categories': Ordinance.CATEGORY_CHOICES,
        'statuses': Ordinance.STATUS_CHOICES,
    })


@login_required
def ordinance_delete(request, pk):
    """Delete an ordinance."""
    ordinance = get_object_or_404(Ordinance, pk=pk)
    if request.method == 'POST':
        ordinance.delete()
        messages.success(request, 'Ordinance deleted.')
        return redirect('ordinances:list')
    return render(request, 'ordinances/confirm_delete.html', {'ordinance': ordinance})


@login_required
def ordinance_download(request, pk):
    """Download ordinance document."""
    ordinance = get_object_or_404(Ordinance, pk=pk)
    if ordinance.document_file:
        return FileResponse(ordinance.document_file.open(), as_attachment=True,
                            filename=f"Ordinance_{ordinance.ordinance_number}.pdf")
    messages.error(request, 'No document file attached.')
    return redirect('ordinances:view', pk=pk)
