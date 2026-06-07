# blog/management/commands/create_posts.py

import os
import random
import requests
import time
import json
import sys
from io import BytesIO
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.db.models import Max
from django.utils.text import slugify

# Classe de Comando Principal
class Command(BaseCommand):
    help = "Cria posts de blog em português a partir de temas, adaptado para django-parler."
    
    # Linguagem padrão para todo o conteúdo gerado
    LANGUAGE_CODE = 'pt-br'

    def add_arguments(self, parser):
        parser.add_argument(
            '--themes', nargs='+', type=str, required=True,
            help='Uma lista de temas para gerar artigos. Ex: "IA na Medicina" "Futuro do Django"'
        )
        parser.add_argument(
            '--count', type=int, default=1,
            help='Número de artigos para gerar por tema. Padrão: 1.'
        )
        parser.add_argument(
            '--model', type=str, default='llama3-70b-8192',
            help='O modelo da Groq a ser usado. Padrão: llama3-70b-8192.'
        )

    def _unique_translated_slug(self, model_class, base_title: str) -> str:
        """Gera um slug único verificando o campo traduzido com Parler."""
        base_slug = slugify(base_title)
        slug = base_slug
        counter = 1
        while model_class.objects.filter(translations__slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def _get_image_candidates_from_pexels(self, pexels_api, query: str, count: int = 15):
        if not pexels_api: return []
        self.stdout.write(f"🔎 Buscando imagens no Pexels para: '{query}'...")
        try:
            pexels_api.search(query=query, page=random.randint(1, 5), results_per_page=count)
            photos = pexels_api.get_entries()
            if not photos:
                self.stdout.write(self.style.WARNING(f"⚠️ Nenhuma imagem encontrada para '{query}'."))
            return photos
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro ao buscar no Pexels: {e}"))
        return []

    def _select_best_image_with_ia(self, groq_client, model_name: str, section_content: dict, image_candidates: list):
        self.stdout.write("🤖 IA analisando a relevância das imagens...")
        descriptions_list = "\n".join([f"{i+1}. {photo.description}" for i, photo in enumerate(image_candidates)])
        
        prompt = f"""
        Contexto do Artigo: "{section_content.get('subtitulo', '')}. {' '.join(section_content.get('paragrafos', []))}"
        Tarefa: Analise o contexto e escolha a imagem mais relevante da lista de descrições abaixo.
        **Diretriz Principal: Priorize fotos realistas e claras que representem o tema de forma literal. Evite imagens excessivamente artísticas, conceituais ou abstratas.**
        Responda APENAS com o número da imagem escolhida.
        Lista de Descrições de Imagens:
        {descriptions_list}
        """
        try:
            completion = groq_client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": prompt}], temperature=0.1)
            response_text = completion.choices[0].message.content.strip()
            best_index_str = ''.join(filter(str.isdigit, response_text))
            if best_index_str:
                best_index = int(best_index_str) - 1
                if 0 <= best_index < len(image_candidates):
                    self.stdout.write(self.style.SUCCESS(f"👍 IA escolheu a imagem #{best_index + 1}."))
                    return image_candidates[best_index]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro na análise da IA: {e}."))
        self.stdout.write(self.style.WARNING("⚠️ Análise da IA falhou. Retornando None."))
        return None

    def download_image_content(self, image_url: str) -> ContentFile | None:
        if not image_url: return None
        try:
            self.stdout.write(f"⬇️ Baixando imagem de: {image_url}")
            response = requests.get(image_url, timeout=20)
            response.raise_for_status()
            return ContentFile(response.content)
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ Falha ao baixar imagem: {e}"))
        return None

    def generate_article_data(self, client, topic: str, model_name: str) -> dict | None:
        self.stdout.write(f"🤖 Gerando estrutura do artigo sobre '{topic}' em português...")
        prompt = f"""
        Você é um especialista em redação de artigos para blogs em português do Brasil. Sua tarefa é criar um artigo completo sobre: "{topic}".
        O título deve ser único e em português. Siga ESTRITAMENTE a estrutura JSON abaixo, criando PELO MENOS 3 seções:
        {{
          "titulo": "Um título criativo e chamativo em português.",
          "categoria": "Sugira uma única categoria em português para o post.",
          "introducao": "Um parágrafo de introdução envolvente.",
          "secoes": [
            {{"subtitulo": "Subtítulo da seção 1.", "paragrafos": ["..."], "query_imagem": "Palavras-chave em inglês para a imagem da seção 1."}},
            {{"subtitulo": "Subtítulo da seção 2.", "paragrafos": ["..."], "query_imagem": "Palavras-chave em inglês para a imagem da seção 2."}},
            {{"subtitulo": "Subtítulo da seção 3.", "paragrafos": ["..."], "query_imagem": "Palavras-chave em inglês para a imagem da seção 3."}}
          ],
          "conclusao": "Um parágrafo de conclusão."
        }}
        """
        try:
            completion = client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": prompt}], temperature=0.8, max_tokens=4096, stream=False, response_format={"type": "json_object"})
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro fatal ao gerar conteúdo: {e}"))
        return None

    def _get_image_with_fallbacks(self, groq_client, pexels_api, llm_model, secao, topic, used_image_ids):
        GUARANTEED_FALLBACK_URL = 'https://images.pexels.com/photos/3861958/pexels-photo-3861958.jpeg'
        
        if not pexels_api:
            return {'large': GUARANTEED_FALLBACK_URL, 'description': topic}

        base_query = secao.get('query_imagem', '')
        detailed_query = f"{topic}, {base_query}, technology, data"
        
        candidates = self._get_image_candidates_from_pexels(pexels_api, detailed_query)
        new_candidates = [p for p in candidates if p.id not in used_image_ids]

        if new_candidates:
            best_photo = self._select_best_image_with_ia(groq_client, llm_model, secao, new_candidates)
            if best_photo:
                used_image_ids.add(best_photo.id)
                return best_photo
            
            self.stdout.write(self.style.WARNING("Fallback: Escolhendo imagem aleatória."))
            random_photo = random.choice(new_candidates)
            used_image_ids.add(random_photo.id)
            return random_photo
            
        self.stdout.write(self.style.WARNING("Fallback: Busca detalhada falhou, tentando busca simples."))
        simple_query = f"{topic}, {base_query}"
        candidates = self._get_image_candidates_from_pexels(pexels_api, simple_query)
        new_candidates = [p for p in candidates if p.id not in used_image_ids]

        if new_candidates:
            random_photo = random.choice(new_candidates)
            used_image_ids.add(random_photo.id)
            return random_photo

        self.stdout.write(self.style.ERROR("ERRO FINAL: Nenhuma imagem encontrada. Usando fallback padrão."))
        return {'large': GUARANTEED_FALLBACK_URL, 'description': topic}

    def handle(self, *args, **options):
        from django.conf import settings
        from blog.models import Author, Category, Post
        from groq import Groq
        try:
            from pexels_api import API
            PEXELS_AVAILABLE = True
        except ImportError:
            PEXELS_AVAILABLE = False
        
        GROQ_API_KEY = getattr(settings, 'GROQ_API_KEY', None)
        PEXELS_API_KEY = getattr(settings, 'PEXELS_API_KEY', None)
        themes_to_generate = options['themes']
        posts_per_theme = options['count']
        llm_model = options['model']

        if not GROQ_API_KEY:
            self.stdout.write(self.style.ERROR("❌ Chave GROQ_API_KEY não encontrada nas configurações."))
            return
        
        # --- BLOCO DE VALIDAÇÃO DA PEXELS API ---
        self.stdout.write("\n--- Validação da API Pexels ---")
        pexels_api = None
        if not PEXELS_AVAILABLE:
            self.stdout.write(self.style.ERROR("❌ Biblioteca 'pexels-api' não instalada. Rode: pip install pexels-api"))
        elif not PEXELS_API_KEY:
            self.stdout.write(self.style.ERROR("❌ Chave PEXELS_API_KEY não encontrada. Verifique seu arquivo .env e settings.py."))
        else:
            self.stdout.write(self.style.SUCCESS("✅ Chave PEXELS_API_KEY encontrada."))
            try:
                self.stdout.write("⏳ Testando conexão com a API Pexels...")
                api_test = API(PEXELS_API_KEY)
                api_test.search('test', page=1, results_per_page=1)
                api_test.get_entries()
                self.stdout.write(self.style.SUCCESS("✅ Conexão bem-sucedida! A chave é válida."))
                pexels_api = api_test # Reutiliza a instância testada
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Falha ao conectar com a API Pexels. A chave pode ser inválida ou há um problema de rede."))
                self.stdout.write(self.style.ERROR(f"   Detalhe do erro: {e}"))
        self.stdout.write("---------------------------------\n")
        # --- FIM DO BLOCO DE VALIDAÇÃO ---

        groq_client = Groq(api_key=GROQ_API_KEY)
        
        author, created = Author.objects.get_or_create(
            full_name="Autor Gerado por IA",
            defaults={'email': 'autor.ia@example.com'}
        )
        if created:
            author.set_current_language(self.LANGUAGE_CODE)
            author.role = 'Redator IA'
            author.save()

        max_order = Post.objects.aggregate(max_order=Max("order")).get("max_order") or 0
        next_order = max_order + 1
        
        for topic in themes_to_generate:
            for i in range(posts_per_theme):
                self.stdout.write(f"\n--- Gerando artigo {i+1}/{posts_per_theme} para o tema: '{topic}' ---")
                article_data = self.generate_article_data(groq_client, topic, llm_model)
                if not article_data or not article_data.get('secoes'):
                    self.stdout.write(self.style.WARNING("⚠️ Falha ao gerar dados do artigo. Pulando."))
                    continue

                category_name = article_data.get('categoria', 'Geral')
                
                try:
                    category = Category.objects.language(self.LANGUAGE_CODE).get(translations__name=category_name)
                    created = False
                except Category.DoesNotExist:
                    category_slug = self._unique_translated_slug(Category, category_name)
                    category = Category()
                    category.set_current_language(self.LANGUAGE_CODE)
                    category.name = category_name
                    category.slug = category_slug
                    category.save()
                    created = True

                if created:
                    self.stdout.write(self.style.SUCCESS(f"✅ Categoria '{category_name}' criada. Buscando imagem de capa..."))
                    category_context = {'query_imagem': category_name, 'subtitulo': f'Imagem para {category_name}'}
                    category_image_obj = self._get_image_with_fallbacks(groq_client, pexels_api, llm_model, category_context, category_name, set())
                    if hasattr(category_image_obj, 'original'):
                        category_image_content = self.download_image_content(category_image_obj.original)
                        if category_image_content:
                            category.image.save(f"{category.slug}.jpg", category_image_content, save=True)
                            self.stdout.write(self.style.SUCCESS(f"🖼️ Imagem de capa atribuída à categoria '{category_name}'."))
                            category.refresh_from_db()

                html_content = f"<p>{article_data['introducao']}</p>"
                used_image_ids = set()
                thumbnail_content = None

                for idx, secao in enumerate(article_data.get('secoes', [])):
                    html_content += f"<h2>{secao.get('subtitulo', '')}</h2>"
                    
                    image_obj = self._get_image_with_fallbacks(groq_client, pexels_api, llm_model, secao, topic, used_image_ids)
                    image_url = image_obj.large if hasattr(image_obj, 'large') else image_obj.get('large')
                    image_alt = image_obj.description if hasattr(image_obj, 'description') else image_obj.get('description', '')
                    
                    if image_url:
                        html_content += f'<img src="{image_url}" alt="{image_alt}" style="max-width:100%; height:auto; border-radius:8px; margin:1.5rem 0;">'

                    if idx == 0 and hasattr(image_obj, 'original'):
                         thumbnail_content = self.download_image_content(image_obj.original)

                    for paragrafo in secao.get('paragrafos', []):
                        html_content += f"<p>{paragrafo}</p>"

                html_content += f"<h2>Conclusão</h2><p>{article_data.get('conclusao', '')}</p>"

                post_slug = self._unique_translated_slug(Post, article_data['titulo'])
                
                post = Post(author=author, category=category, status="published", order=next_order)
                
                post.set_current_language(self.LANGUAGE_CODE)
                post.title = article_data['titulo']
                post.slug = post_slug
                post.content = html_content

                if thumbnail_content:
                    post.thumbnail.save(f"{post.slug}.jpg", thumbnail_content, save=False)
                    self.stdout.write(self.style.SUCCESS("✅ Imagem de destaque (thumbnail) definida."))
                
                post.save()
                self.stdout.write(self.style.SUCCESS(f"✅ Post '{post.title}' criado e publicado."))
                next_order += 1
                time.sleep(5)

        self.stdout.write(self.style.SUCCESS(f"\n🎉 Processo concluído!"))


# --- Bloco para Execução Direta (sem manage.py) ---
if __name__ == '__main__':
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.append(str(project_root))

    try:
        from dotenv import load_dotenv
        dotenv_path = project_root / '.env'
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path)
            print("INFO: Variáveis de ambiente do arquivo .env foram carregadas.")
        else:
            print("AVISO: Arquivo .env não encontrado na raiz do projeto.")
    except ImportError:
        print("AVISO: Pacote 'python-dotenv' não instalado. As variáveis do .env não serão carregadas.")

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    try:
        import django
        django.setup()
    except ImportError as exc:
        raise ImportError(f"Não foi possível importar o Django. Erro: {exc}")
    except ModuleNotFoundError:
         raise ModuleNotFoundError(f"Não foi possível encontrar o módulo de settings 'core.settings'.")
        
    from django.core.management import call_command
    from argparse import ArgumentParser
    
    parser = ArgumentParser(description='Wrapper para executar o comando create_posts diretamente.')
    parser.add_argument('--themes', nargs='+', type=str, required=True, help='Temas para os artigos.')
    parser.add_argument('--count', type=int, default=1, help='Número de artigos por tema.')
    parser.add_argument('--model', type=str, default='llama3-70b-8192', help='Modelo Groq.')
    args = parser.parse_args(sys.argv[1:])
    
    call_command('create_posts', themes=args.themes, count=args.count, model=args.model)
