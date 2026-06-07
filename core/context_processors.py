# core/context_processors.py

from django.conf import settings

def settings_context(request):
    """
    Injeta configurações globais nos templates para serem usadas em todo o site.
    """
    return {
        'GOOGLE_ADSENSE_PUB_ID': getattr(settings, 'GOOGLE_ADSENSE_PUB_ID', ''),
        'CREATOR_LINKEDIN_URL': getattr(settings, 'CREATOR_LINKEDIN_URL', ''), # <-- ADICIONE ESTA LINHA
    }

