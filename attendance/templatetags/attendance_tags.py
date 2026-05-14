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
    actual_dt = datetime.combine(date.today(), actual_time)
    shift_dt = datetime.combine(date.today(), shift_time)
    diff_sec = (actual_dt - shift_dt).total_seconds()
    
    if diff_sec <= 0:
        return "0 sec"
    
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
