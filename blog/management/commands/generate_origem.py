import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from blog.admin_views import AgentPipeline, ImageEngine
from blog.models import Author, Category, Post

PROMPT = (
    "Escreva sobre a série Origem 4ª temporada da MGM. "
    "Sobre: Uma família viaja em um trailer quando se perde na estrada. "
    "Eles buscam direções em um pequeno povoado, mas logo percebem que estão "
    "presos em um loop e não conseguem deixar o lugar, encurralados por forças misteriosas."
)

MODEL = "openai/gpt-oss-120b"


class Command(BaseCommand):
    help = "Limpa todos os posts e gera 5 matérias sobre Origem 4ª temporada"

    def handle(self, *args, **kwargs):
        api_key = settings.GROQ_API_KEY
        if not api_key:
            self.stderr.write(self.style.ERROR("GROQ_API_KEY não configurada no .env!"))
            return

        # 1. Limpar todos os posts existentes
        count = Post.objects.count()
        Post.objects.all().delete()
        self.stdout.write(self.style.WARNING(f"🗑️  {count} post(s) deletado(s)."))

        # 2. Garantir author e category
        author = Author.objects.first()
        category = Category.objects.first()
        if not author or not category:
            self.stderr.write(self.style.ERROR(
                "Nenhum Author ou Category encontrado. Crie ao menos um de cada no admin."
            ))
            return

        self.stdout.write(f"   Autor: {author.full_name} | Categoria: {category.name}")

        # 3. Gerar 5 matérias
        for i in range(1, 6):
            self.stdout.write(f"\n{'='*55}")
            self.stdout.write(f"🚀 Gerando matéria {i}/5...")

            if i > 1:
                self.stdout.write("   ⏳ Aguardando 90s para respeitar rate limit do Groq...")
                time.sleep(90)

            try:
                pipeline = AgentPipeline(MODEL, api_key)
                result = pipeline.run(PROMPT, variation=i, total=5)

                post = Post()
                post.title = result["title"]
                post.content = result["html"]
                post.category = category
                post.author = author
                post.status = "published"
                post.meta_title = result["meta_title"]
                post.meta_description = result["meta_description"]

                if result.get("cover_url"):
                    img_bytes = ImageEngine.download(result["cover_url"])
                    if img_bytes:
                        fname = f"{slugify(result['title'])[:40]}_cover.jpg"
                        post.thumbnail.save(fname, ContentFile(img_bytes), save=False)

                post.save()
                self.stdout.write(self.style.SUCCESS(f"   ✅ Salva: {result['title']}"))

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"   ❌ Erro na matéria {i}: {e}"))

        self.stdout.write(self.style.SUCCESS("\n🎉 Processo concluído!"))
