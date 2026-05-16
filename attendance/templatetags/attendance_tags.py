from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def add_str(value, arg):
    return f"{value}{arg}"

@register.filter
def range_to(start, end):
    return range(start, end)

@register.filter
def month_name_short(month_num):
    import calendar
    return calendar.month_name[month_num][:3]

@register.filter
def late_duration(actual_time, shift_time):
    if not actual_time or not shift_time:
        return ""
    from datetime import datetime, date
    # Use a dummy date to ensure we only compare times
    dummy = date(2000, 1, 1)
    actual_dt = datetime.combine(dummy, actual_time)
    shift_dt = datetime.combine(dummy, shift_time)
    diff_sec = (actual_dt - shift_dt).total_seconds()
    
    if diff_sec <= 0:
        return ""
    
    if diff_sec < 60:
        return f"{int(diff_sec)} sec"
    elif diff_sec < 3600:
        return f"{int(diff_sec // 60)} mins"
    else:
        hrs = int(diff_sec // 3600)
        mins = int((diff_sec % 3600) // 60)
        if mins > 0:
            return f"{hrs} hrs {mins} mins"
        return f"{hrs} hrs"

@register.simple_tag
def get_lateness(actual_time, shift_time, grace_period=15):
    """
    Returns the lateness duration string ONLY if it exceeds the grace period.
    Otherwise returns an empty string.
    """
    if not actual_time or not shift_time:
        return ""
    
    from datetime import datetime, date
    dummy = date(2000, 1, 1)
    actual_dt = datetime.combine(dummy, actual_time)
    shift_dt = datetime.combine(dummy, shift_time)
    
    diff_sec = (actual_dt - shift_dt).total_seconds()
    
    # If not late at all or within grace period, return empty
    if diff_sec <= (grace_period * 60):
        return ""
        
    # Return the duration string using the existing filter logic
    return late_duration(actual_time, shift_time)

@register.filter
def is_absent_visible(log_date, shift_out_time):
    """
    Returns True if the 'Absent' indicator should be shown.
    For past dates, it's always shown.
    For today, it's only shown after the shift end time (shift_out_time).
    """
    from datetime import datetime, date
    if not log_date: return True
    
    today = date.today()
    if log_date < today:
        return True
    if log_date > today:
        return False
        
    # It's today - check if current time is past shift end
    if not shift_out_time: return True
    return datetime.now().time() > shift_out_time
