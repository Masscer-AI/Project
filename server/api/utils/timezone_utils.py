"""
Utilidades para manejar conversiones de zona horaria.
"""
from django.utils import timezone as django_timezone
from django.utils.dateparse import parse_datetime
import pytz
from datetime import datetime


def convert_to_organization_timezone(utc_datetime, organization_timezone='UTC'):
    """
    Convierte un datetime UTC a la zona horaria de la organización.
    
    Args:
        utc_datetime: datetime en UTC (puede ser datetime, string ISO, o None)
        organization_timezone: string con el nombre del timezone (default: 'UTC')
    
    Returns:
        datetime en la zona horaria de la organización, o None si utc_datetime es None
    """
    if utc_datetime is None:
        return None
    
    # Convertir string a datetime si es necesario
    if isinstance(utc_datetime, str):
        utc_datetime = parse_datetime(utc_datetime)
        if utc_datetime is None:
            return None
    
    # Si ya es aware, usar directamente; si es naive, asumir UTC
    if django_timezone.is_naive(utc_datetime):
        utc_datetime = django_timezone.make_aware(utc_datetime, pytz.UTC)
    
    # Convertir a la zona horaria de la organización
    try:
        org_tz = pytz.timezone(organization_timezone)
        return utc_datetime.astimezone(org_tz)
    except pytz.UnknownTimeZoneError:
        # Si el timezone no es válido, usar UTC
        return utc_datetime.astimezone(pytz.UTC)


def format_datetime_for_organization(utc_datetime, organization_timezone='UTC', format_str='%Y-%m-%d %H:%M:%S %Z'):
    """
    Formatea un datetime UTC según la zona horaria de la organización.
    
    Args:
        utc_datetime: datetime en UTC
        organization_timezone: string con el nombre del timezone
        format_str: formato de salida (default: '%Y-%m-%d %H:%M:%S %Z')
    
    Returns:
        string formateado o None
    """
    converted = convert_to_organization_timezone(utc_datetime, organization_timezone)
    if converted is None:
        return None
    return converted.strftime(format_str)


def get_organization_timezone_from_request(request):
    """
    Obtiene la zona horaria de la organización del usuario desde el request.
    
    Args:
        request: HttpRequest con el usuario
    
    Returns:
        string con el timezone o 'UTC' por defecto
    """
    if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
        return 'UTC'
    
    from api.authenticate.models import Organization
    from api.authenticate.models import UserProfile
    
    # Intentar obtener la organización del perfil del usuario
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.organization:
            return profile.organization.timezone
    except UserProfile.DoesNotExist:
        pass
    
    # Fallback: obtener la primera organización donde el usuario es owner
    try:
        org = Organization.objects.filter(owner=request.user).first()
        if org:
            return org.timezone
    except Exception:
        pass
    
    return 'UTC'

