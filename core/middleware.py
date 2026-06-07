from django.shortcuts import redirect
from django.conf import settings

class AdminAnywhereMiddleware:
    """
    Middleware que intercepta qualquer URL que termine com /admin ou /admin/
    e redireciona para a raiz do painel administrativo.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        
        # Verifica se a URL termina com admin ou admin/
        if path.endswith('/admin') or path.endswith('/admin/'):
            parts = [p for p in path.split('/') if p]
            
            # Garante que 'admin' seja o último segmento
            if len(parts) > 0 and parts[-1] == 'admin':
                lang_codes = [lang[0] for lang in settings.LANGUAGES]
                
                # Ignora as rotas raiz do admin para evitar loop de redirecionamento
                if len(parts) == 1:
                    # Ex: /admin/
                    pass 
                elif len(parts) == 2 and parts[0] in lang_codes:
                    # Ex: /pt-br/admin/ ou /en/admin/
                    pass 
                else:
                    # Qualquer outra rota (ex: /pt-br/artigos/meu-artigo/admin)
                    # Redireciona para /admin/ (o LocaleMiddleware vai cuidar do idioma)
                    return redirect('/admin/')
                    
        return self.get_response(request)
