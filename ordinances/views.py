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
    if request.user.get_permission_level() > 2:
        messages.error(request, 'You do not have permission to add ordinances.')
        return redirect('ordinances:list')
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
    if request.user.get_permission_level() > 2:
        messages.error(request, 'You do not have permission to edit ordinances.')
        return redirect('ordinances:list')
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
    if request.user.get_permission_level() > 2:
        messages.error(request, 'You do not have permission to delete ordinances.')
        return redirect('ordinances:list')
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


import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from .utils import parse_ordinance_pdf


@login_required
def ordinance_upload_parse(request):
    """Handle PDF upload, parse it, and render the review form."""
    if request.user.get_permission_level() > 2:
        messages.error(request, 'You do not have permission to upload ordinances.')
        return redirect('ordinances:list')
    if request.method == 'POST' and request.FILES.get('document_file'):
        pdf_file = request.FILES['document_file']

        # Save file temporarily to parse it
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'temp_ordinances'))
        filename = fs.save(pdf_file.name, pdf_file)
        file_path = fs.path(filename)

        # Parse the PDF
        parsed_data = parse_ordinance_pdf(file_path)

        # Build URL to preview the temp file
        file_url = f"/media/temp_ordinances/{filename}"

        context = {
            'parsed_data': parsed_data,
            'file_url': file_url,
            'temp_filename': filename,
            'categories': Ordinance.CATEGORY_CHOICES,
            'statuses': Ordinance.STATUS_CHOICES,
        }
        return render(request, 'ordinances/parse_review.html', context)

    elif request.method == 'POST' and 'save_ordinance' in request.POST:
        # This is the submission from the parse_review form
        ord_num = request.POST.get('ordinance_number')
        try:
            ordinance = Ordinance.objects.get(ordinance_number=ord_num)
            msg = f'Ordinance {ordinance.ordinance_number} updated successfully.'
        except Ordinance.DoesNotExist:
            ordinance = Ordinance(ordinance_number=ord_num)
            msg = f'Ordinance {ordinance.ordinance_number} parsed and created successfully.'

        ordinance.title = request.POST.get('title')
        ordinance.description = request.POST.get('description', '')
        ordinance.author = request.POST.get('author')
        ordinance.date_enacted = request.POST.get('date_enacted') or '2024-01-01'
        ordinance.date_effectivity = request.POST.get('date_effectivity') or None
        ordinance.category = request.POST.get('category', 'other')
        ordinance.status = request.POST.get('status', 'active')
        ordinance.sponsor = request.POST.get('sponsor', '')
        ordinance.remarks = request.POST.get('remarks', '')
        ordinance.body_content = request.POST.get('body_content', '')
        ordinance.signatories = request.POST.get('signatories', '')

        # Move the temp file to the permanent location
        temp_filename = request.POST.get('temp_filename')
        if temp_filename:
            temp_path = os.path.join(settings.MEDIA_ROOT, 'temp_ordinances', temp_filename)
            if os.path.exists(temp_path):
                from django.core.files import File
                with open(temp_path, 'rb') as f:
                    ordinance.document_file.save(temp_filename, File(f), save=False)
                ordinance.save()
                os.remove(temp_path)
            else:
                ordinance.save()
        else:
            ordinance.save()

        messages.success(request, msg)
        return redirect('ordinances:view', pk=ordinance.pk)

    return render(request, 'ordinances/upload.html')
