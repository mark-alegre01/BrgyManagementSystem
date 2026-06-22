from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms
from .models import Appointment
from residents.models import Resident

class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['purpose', 'specification', 'appointment_date', 'appointment_time']
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time'}),
            'specification': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional: Add more details...'}),
        }

@login_required
def book_appointment(request):
    try:
        resident = request.user.profile.resident
    except AttributeError:
        messages.error(request, 'Your account is not linked to a resident record. Please contact the secretary.')
        return redirect('dashboard')

    if not resident:
        messages.error(request, 'Your account is not linked to a resident record. Please contact the secretary.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.resident = resident
            appointment.save()
            messages.success(request, 'Appointment booked successfully! Please wait for approval.')
            return redirect('appointment_list')
    else:
        form = AppointmentForm()
    
    return render(request, 'appointments/book.html', {'form': form})

@login_required
def appointment_list(request):
    try:
        role = request.user.profile.role
    except AttributeError:
        role = 'resident'

    if role in ('captain', 'secretary', 'treasurer', 'admin', 'staff'):
        appointments = Appointment.objects.all().order_by('-created_at')
        template = 'appointments/manage.html'
    else:
        resident = request.user.profile.resident
        appointments = Appointment.objects.filter(resident=resident).order_by('-created_at') if resident else []
        template = 'appointments/list.html'
    
    return render(request, template, {'appointments': appointments})

@login_required
def appointment_status_update(request, pk, status):
    if request.user.profile.role not in ('captain', 'secretary', 'treasurer', 'admin'):
        messages.error(request, 'Unauthorized.')
        return redirect('dashboard')
    
    appointment = get_object_or_404(Appointment, pk=pk)
    appointment.status = status
    appointment.save()
    messages.success(request, f'Appointment marked as {status}.')
    return redirect('appointment_list')
