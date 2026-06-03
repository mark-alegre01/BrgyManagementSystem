from django import template
from datetime import date

register = template.Library()

@register.filter
def is_expired(roster_obj):
    return roster_obj.expiry_date < date.today()
