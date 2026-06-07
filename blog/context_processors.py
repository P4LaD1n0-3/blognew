# blog/context_processors.py

from .models import SiteSettings

def site_settings_processor(request):
    """
    Adiciona o objeto de configurações do site ao contexto de todos os templates.
    has_translation_api: True quando a chave Groq está configurada — controla o seletor de idioma.
    """
    try:
        site_settings = SiteSettings.load()
    except SiteSettings.DoesNotExist:
        site_settings = None
    return {
        'site_settings': site_settings,
        'has_translation_api': bool(site_settings and site_settings.groq_api_key),
    }