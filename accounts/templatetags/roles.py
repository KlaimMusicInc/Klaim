from django import template

register = template.Library()


@register.filter
def has_group(user, group_name: str) -> bool:
    try:
        return user.is_authenticated and user.groups.filter(name=group_name).exists()
    except Exception:
        return False


@register.filter
def has_any_group(user, groups_csv: str) -> bool:
    """
    Uso: {{ request.user|has_any_group:"Administrador,SuperStaff" }}
    """
    try:
        if not user.is_authenticated:
            return False
        names = [g.strip() for g in groups_csv.split(",") if g.strip()]
        return user.groups.filter(name__in=names).exists()
    except Exception:
        return False
