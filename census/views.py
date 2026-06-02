from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from residents.models import Resident, Household
from datetime import date


@login_required
def census_dashboard(request):
    """Census overview with population stats."""
    residents = Resident.objects.filter(is_active=True)
    total = residents.count()
    
    total_households = Household.objects.count()
    avg_household_size = round(total / total_households, 1) if total_households > 0 else 0

    # Age groups
    today = date.today()
    age_groups = {
        'Infant (0-1)': 0,
        'Early Childhood (2-5)': 0,
        'Child (6-12)': 0,
        'Teenager (13-17)': 0,
        'Young Adult (18-24)': 0,
        'Adult (25-59)': 0,
        'Senior Citizen (60+)': 0,
    }

    for r in residents:
        ag = r.age_group
        if ag == 'Infant':
            age_groups['Infant (0-1)'] += 1
        elif ag == 'Early Childhood':
            age_groups['Early Childhood (2-5)'] += 1
        elif ag == 'Child':
            age_groups['Child (6-12)'] += 1
        elif ag == 'Teenager':
            age_groups['Teenager (13-17)'] += 1
        elif ag == 'Young Adult':
            age_groups['Young Adult (18-24)'] += 1
        elif ag == 'Adult':
            age_groups['Adult (25-59)'] += 1
        elif ag == 'Senior Citizen':
            age_groups['Senior Citizen (60+)'] += 1

    # Gender
    male_count = residents.filter(gender='M').count()
    female_count = residents.filter(gender='F').count()

    # Civil status
    civil_stats = residents.values('civil_status').annotate(count=Count('id'))

    # Purok
    purok_stats = residents.values('purok').annotate(count=Count('id')).order_by('purok')

    # Voter
    voters = residents.filter(is_registered_voter=True).count()
    pwd = residents.filter(is_pwd=True).count()
    senior = residents.filter(is_senior_citizen=True).count()
    fourps = residents.filter(is_4ps_member=True).count()

    context = {
        'total_population': total,
        'total_households': total_households,
        'avg_household_size': avg_household_size,
        'age_groups': age_groups,
        'male_count': male_count,
        'female_count': female_count,
        'civil_stats': {cs['civil_status']: cs['count'] for cs in civil_stats},
        'purok_stats': list(purok_stats),
        'voters': voters,
        'pwd': pwd,
        'senior': senior,
        'fourps': fourps,
        'age_group_labels': list(age_groups.keys()),
        'age_group_values': list(age_groups.values()),
    }
    return render(request, 'census/dashboard.html', context)


@login_required
def age_groups(request):
    """Detailed age group breakdown."""
    residents = Resident.objects.filter(is_active=True)

    groups = {}
    for r in residents:
        ag = r.age_group
        if ag not in groups:
            groups[ag] = {'male': 0, 'female': 0, 'total': 0, 'residents': []}
        groups[ag]['total'] += 1
        if r.gender == 'M':
            groups[ag]['male'] += 1
        else:
            groups[ag]['female'] += 1
        groups[ag]['residents'].append(r)

    ordered_groups = ['Infant', 'Early Childhood', 'Child', 'Teenager', 'Young Adult', 'Adult', 'Senior Citizen']
    ordered_data = []
    for g in ordered_groups:
        if g in groups:
            ordered_data.append({'name': g, **groups[g]})

    return render(request, 'census/age_groups.html', {'age_groups': ordered_data})


@login_required
def demographics(request):
    """Demographics data with charts."""
    residents = Resident.objects.filter(is_active=True)

    # By purok
    purok_data = residents.values('purok').annotate(
        total=Count('id'),
        male=Count('id', filter=Q(gender='M')),
        female=Count('id', filter=Q(gender='F')),
    ).order_by('purok')

    # By nationality
    nationality_data = residents.values('nationality').annotate(count=Count('id'))

    # By religion
    religion_data = residents.values('religion').annotate(count=Count('id')).order_by('-count')[:10]

    # By occupation
    occupation_data = residents.values('occupation').annotate(count=Count('id')).order_by('-count')[:10]

    context = {
        'purok_data': list(purok_data),
        'nationality_data': list(nationality_data),
        'religion_data': list(religion_data),
        'occupation_data': list(occupation_data),
    }
    return render(request, 'census/demographics.html', context)
