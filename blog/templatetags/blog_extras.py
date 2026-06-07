# blog/templatetags/blog_extras.py

import re
from django import template
from django.utils.html import strip_tags

register = template.Library()

@register.filter(name='reading_time')
def reading_time(html_content):
    """
    Estima o tempo de leitura em minutos para um determinado conteúdo HTML.
    Remove as tags HTML e conta as palavras.
    Assume uma velocidade de leitura média de 200 palavras por minuto.
    """
    try:
        # Remove tags HTML do conteúdo
        text_content = strip_tags(html_content)

        # Conta as palavras
        word_count = len(re.findall(r'\w+', text_content))

        # Calcula o tempo de leitura (palavras / palavras por minuto)
        minutes = word_count / 200

        # Arredonda para o número inteiro mais próximo
        rounded_minutes = round(minutes)

        # Garante que o resultado seja no mínimo 1 minuto
        if rounded_minutes < 1:
            return "Menos de 1 min de leitura"
        elif rounded_minutes == 1:
            return "1 min de leitura"
        else:
            return f"{rounded_minutes} min de leitura"
    except:
        # Fallback em caso de erro
        return "Tempo de leitura indisponível"