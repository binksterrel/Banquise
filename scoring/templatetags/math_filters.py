from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """
    Multiplie la valeur par l'argument.
    Utilisation: {{ some_value|multiply:5 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def subtract(value, arg):
    """
    Soustrait l'argument de la valeur.
    Utilisation: {{ some_value|subtract:5 }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return '' 