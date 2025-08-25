from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    """Permite acceder a diccionarios con una clave dinámica en templates: {{ dict|get_item:variable }}"""
    try:
        return d.get(key)
    except Exception:
        return None
