# blog/models.py

from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from tinymce.models import HTMLField
from parler.models import TranslatableModel, TranslatedFields
from django.core.exceptions import ValidationError
from django.conf import settings

class SiteSettings(TranslatableModel):
    # ... (código deste modelo permanece o mesmo)
    translations = TranslatedFields(
        site_name = models.CharField(max_length=100, default="MudarNome", verbose_name="Nome do Site")
    )
    instagram_url = models.URLField(blank=True, verbose_name="URL do Instagram")
    linkedin_url = models.URLField(blank=True, verbose_name="URL do LinkedIn")
    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Número do WhatsApp",
        help_text="Apenas números, incluindo código do país e DDD. Ex: 5511999999999"
    )
    posts_in_home_grid = models.PositiveIntegerField(
        default=8,
        verbose_name="Nº de Posts na Grade da Página Inicial",
        help_text="Defina quantos posts (excluindo o de destaque) devem aparecer na seção 'Artigos Recentes'."
    )
    favicon = models.ImageField(
        upload_to='favicons/',
        blank=True,
        null=True,
        verbose_name="Ícone do Site (Favicon)",
        help_text="Faça o upload de uma imagem (.ico, .png, .svg) para ser o ícone nas abas do navegador."
    )
    logo = models.ImageField(
        upload_to='logos/',
        blank=True,
        null=True,
        verbose_name="Logo do Site",
        help_text="Faça o upload da imagem do logo para o cabeçalho. Se deixado em branco, o nome do site será usado como texto."
    )
    show_name_with_logo = models.BooleanField(
        default=False,
        verbose_name="Exibir nome do site junto com o logo?",
        help_text="Se marcado, o nome do site aparecerá ao lado da imagem do logo no cabeçalho."
    )
    groq_api_key = models.CharField(
        max_length=250,
        blank=True,
        verbose_name="Chave API Groq (Tradução Automática)",
        help_text=(
            "Se configurada, cada post salvo será traduzido automaticamente para Inglês, "
            "Espanhol e Francês. Também ativa o seletor de idioma no rodapé do site."
        ),
    )

    class Meta:
        verbose_name = "Configurações do Site"
        verbose_name_plural = "Configurações do Site"

    def __str__(self):
        return self.safe_translation_getter('site_name', any_language=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class Author(TranslatableModel):
    # ... (código deste modelo permanece o mesmo)
    translations = TranslatedFields(
        role = models.CharField(max_length=100, blank=True, verbose_name="Cargo (Ex: Editor-Chefe)"),
        bio = models.TextField(blank=True, verbose_name="Biografia")
    )
    full_name = models.CharField(max_length=255, verbose_name="Nome Completo")
    first_name = models.CharField(max_length=100, editable=False, verbose_name="Primeiro Nome")
    last_name = models.CharField(max_length=155, editable=False, blank=True, verbose_name="Sobrenome")
    email = models.EmailField(unique=True, verbose_name="Email")
    profile_picture = models.ImageField(upload_to='authors/', null=True, blank=True, verbose_name="Foto de Perfil")
    linkedin_url = models.URLField(blank=True, verbose_name="URL do LinkedIn")
    instagram_url = models.URLField(blank=True, verbose_name="URL do Instagram")
    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="WhatsApp",
        help_text="Apenas números, incluindo código do país e DDD. Ex: 5511999999999"
    )
    is_team_member = models.BooleanField(default=True, verbose_name="É membro da equipe principal?")
    # O slug deste modelo é gerado a partir de full_name, que não é traduzível,
    # então o método save dele já está correto e mais simples. Não precisa de alteração.
    slug = models.SlugField(max_length=255, unique=True, editable=False)

    class Meta:
        verbose_name = "Autor (e Membro da Equipe)"
        verbose_name_plural = "Autores (e Membros da Equipe)"
        ordering = ['full_name']

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        parts = self.full_name.split()
        self.first_name = parts[0]
        self.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        # Sempre gera o slug a partir do nome completo
        self.slug = slugify(self.full_name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:author_detail', args=[self.slug, self.pk])


class Category(TranslatableModel):
    # ... (sem alterações nos campos) ...
    COLOR_CHOICES = [
        ('#94a3b8', 'Cinza'), ('#f87171', 'Vermelho'), ('#fb923c', 'Laranja'),
        ('#fbbf24', 'Âmbar'), ('#86efac', 'Lima'), ('#4ade80', 'Verde'),
        ('#67e8f9', 'Ciano'), ('#60a5fa', 'Azul'), ('#818cf8', 'Índigo'),
        ('#a78bfa', 'Violeta'),
    ]
    translations = TranslatedFields(
        name = models.CharField(max_length=100, verbose_name="Nome da Categoria"),
        slug = models.SlugField(max_length=100, unique=True)
    )
    image = models.ImageField(upload_to='category_images/', blank=True, null=True, verbose_name="Imagem da Categoria")
    color = models.CharField(max_length=7, choices=COLOR_CHOICES, default='#94a3b8', blank=True, null=True, verbose_name="Cor da Categoria")

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.safe_translation_getter('name', any_language=True)
    
    def get_absolute_url(self):
        return reverse('blog:posts_by_category', args=[self.slug])

    def clean(self):
        # ... (código deste método permanece o mesmo) ...
        super().clean()
        if not self.name:
            return
        query = Category.objects.filter(
            translations__language_code=self.get_current_language(),
            translations__name__iexact=self.name
        )
        if self.pk:
            query = query.exclude(pk=self.pk)
        if query.exists():
            raise ValidationError({
                'name': f'Uma categoria com o nome "{self.name}" já existe. Por favor, escolha outro nome.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        
        # ✅ ALTERAÇÃO CRÍTICA: A condição "if not self.slug" foi removida.
        # Isso FORÇA o slug a ser regerado a partir do nome a CADA vez que o objeto é salvo.
        current_lang = self.get_current_language()
        try:
            default_language_code = settings.PARLER_LANGUAGES['default']['code']
            self.set_current_language(default_language_code)
            # Se o nome estiver vazio, slugify('') retorna '', zerando o slug.
            self.slug = slugify(self.name)
        finally:
            self.set_current_language(current_lang)

        super().save(*args, **kwargs)


class Post(TranslatableModel):
    # ... (sem alterações nos campos) ...
    STATUS_CHOICES = (('draft', 'Rascunho'), ('published', 'Publicado'))
    translations = TranslatedFields(
        title = models.CharField(max_length=200, verbose_name="Título"),
        slug = models.SlugField(max_length=200, unique=True, help_text="Este campo será preenchido automaticamente."),
        content = HTMLField(verbose_name="Conteúdo"),
        meta_title = models.CharField(
            max_length=60,
            blank=True,
            verbose_name="Título para SEO (Meta Title)",
            help_text="Otimizado para buscadores (máx. 60 caracteres). Se vazio, usa o título principal."
        ),
        meta_description = models.CharField(
            max_length=160,
            blank=True,
            verbose_name="Descrição para SEO (Meta Description)",
            help_text="Resumo atrativo para o Google (máx. 160 caracteres)."
        ),
    )
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True, related_name='posts', verbose_name="Autor")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='posts', verbose_name="Categoria")
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True, verbose_name="Imagem de Destaque")
    keywords = models.CharField(
        max_length=300, blank=True, default='',
        verbose_name="Palavras-chave",
        help_text="Separadas por vírgula. Geradas pelo pipeline IA para artigos relacionados.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published', verbose_name="Status")
    order = models.PositiveIntegerField(default=0, editable=False, db_index=True, verbose_name="Ordem")

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ('order',)

    def __str__(self):
        return self.safe_translation_getter('title', any_language=True)
    
    def get_absolute_url(self):
        # A lógica do get_absolute_url pode precisar de um try-except se o slug puder ser temporariamente vazio
        try:
            if self.category:
                return reverse('blog:post_detail', kwargs={
                    'category_slug': self.category.slug,
                    'post_slug': self.slug
                })
        except Exception:
            return reverse('blog:home')
        return reverse('blog:home')

    def clean(self):
        # ... (código deste método permanece o mesmo) ...
        super().clean()
        if not self.title:
            return
        query = Post.objects.filter(
            translations__language_code=self.get_current_language(),
            translations__title__iexact=self.title
        )
        if self.pk:
            query = query.exclude(pk=self.pk)
        if query.exists():
            raise ValidationError({
                'title': f'Um post com o título "{self.title}" já existe. Por favor, escolha outro título.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        
        # ✅ ALTERAÇÃO CRÍTICA: Mesma lógica aplicada aqui para o Post.
        # O slug sempre será um reflexo do título.
        current_lang = self.get_current_language()
        try:
            default_language_code = settings.PARLER_LANGUAGES['default']['code']
            self.set_current_language(default_language_code)
            self.slug = slugify(self.title)
        finally:
            self.set_current_language(current_lang)

        super().save(*args, **kwargs)


# ... (restante do arquivo models.py sem alterações) ...
class AboutPage(TranslatableModel):
    translations = TranslatedFields(
        title = models.CharField(max_length=200, verbose_name="Título Principal"),
        content = HTMLField(verbose_name="Conteúdo Completo da Página")
    )
    header_image = models.ImageField(upload_to='about_page/', blank=True, null=True, verbose_name="Imagem de Cabeçalho")
    class Meta:
        verbose_name = "Página Sobre"
        verbose_name_plural = "Página Sobre"
    def __str__(self):
        return self.safe_translation_getter('title', any_language=True)


class ContactSubmission(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome")
    email = models.EmailField(verbose_name="Email")
    message = models.TextField(verbose_name="Mensagem")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Enviado em")
    class Meta:
        verbose_name = "Mensagem de Contato"
        verbose_name_plural = "Mensagens de Contato"
        ordering = ('-submitted_at',)
    def __str__(self):
        return f"Mensagem de {self.name} ({self.email})"


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True, verbose_name="E-mail do Assinante")
    subscribed_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Inscrição")
    class Meta:
        verbose_name = "Assinante da Newsletter"
        verbose_name_plural = "Assinantes da Newsletter"
        ordering = ('-subscribed_at',)
    def __str__(self):
        return self.email