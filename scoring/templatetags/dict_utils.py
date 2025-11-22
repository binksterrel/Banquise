from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


@register.filter
def ratio(value, max_value):
    try:
        v = float(value or 0)
        m = float(max_value or 0)
        if m <= 0:
            return 0
        return min(v / m, 1)
    except (TypeError, ValueError):
        return 0
