# blog/admin.py

from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django.utils.http import urlencode
from django.db.models import Count
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from .models import (
    AboutPage, NewsletterSubscriber, Post, Category, 
    Author, ContactSubmission, SiteSettings
)
from adminsortable2.admin import SortableAdminMixin
from parler.admin import TranslatableAdmin

# --- Site Administrativo Customizado ---
class CustomAdminSite(admin.AdminSite):
    def each_context(self, request):
        context = super().each_context(request)
        try:
            site_settings = SiteSettings.load()
            if site_settings:
                context['site_header'] = site_settings.site_name
                context['site_title'] = f"Admin de {site_settings.site_name}"
        except Exception:
            context['site_header'] = "Painel Administrativo"
            context['site_title'] = "Administração do Site"
        return context

    def get_urls(self):
        from django.urls import path
        from .admin_views import (
            AIWriterView, AISettingsView,
            FormatContentView, TranslatePostView, GenerateSEOView,
        )
        urls = super().get_urls()
        custom_urls = [
            path('blog/ai-writer/',         self.admin_view(AIWriterView.as_view()),      name='ai_writer'),
            path('blog/ai-settings/',       self.admin_view(AISettingsView.as_view()),    name='ai_settings'),
            path('blog/ai-format-content/', self.admin_view(FormatContentView.as_view()), name='ai_format_content'),
            path('blog/ai-translate-post/', self.admin_view(TranslatePostView.as_view()), name='ai_translate_post'),
            path('blog/ai-generate-seo/',   self.admin_view(GenerateSEOView.as_view()),   name='ai_generate_seo'),
        ]
        return custom_urls + urls

site = CustomAdminSite(name='custom_admin')

# --- Registro dos Modelos do App 'blog' ---

@admin.register(SiteSettings, site=site)
class SiteSettingsAdmin(TranslatableAdmin):
    readonly_fields = ('favicon_preview', 'logo_preview')
    fieldsets = (
        ('Branding do Cabeçalho', {
            'fields': ('site_name', ('logo', 'logo_preview'), 'show_name_with_logo')
        }),
        ('Configurações Gerais', {
            'fields': ('posts_in_home_grid', ('favicon', 'favicon_preview'))
        }),
        ('Redes Sociais', {'fields': ('instagram_url', 'linkedin_url', 'whatsapp_number')}),
        ('Tradução Automática por IA', {
            'fields': ('groq_api_key',),
            'description': (
                'Se a chave estiver preenchida, cada post salvo será traduzido automaticamente '
                'para Inglês, Espanhol e Francês. O seletor de idioma no rodapé do site '
                'também só aparece quando esta chave está configurada.'
            ),
        }),
    )
     
    @admin.display(description='Pré-visualização do Favicon')
    def favicon_preview(self, obj):
        if obj.favicon:
            return format_html(f'<img src="{obj.favicon.url}" style="height: 32px; width: 32px;" />')
        return "Nenhum ícone enviado."

    @admin.display(description='Pré-visualização do Logo')
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(f'<img src="{obj.logo.url}" style="max-height: 40px; width: auto; background: #f1f1f1; padding: 5px; border-radius: 3px;" />')
        return "Nenhum logo enviado."

    def has_add_permission(self, request): return not SiteSettings.objects.exists()
    def has_delete_permission(self, request, obj=None): return False

@admin.register(Author, site=site)
class AuthorAdmin(TranslatableAdmin):
    list_display = ('full_name', 'role', 'email', 'is_team_member', 'profile_picture_preview', 'view_posts_link')
    list_filter = ('is_team_member',)
    list_editable = ('is_team_member',)
    search_fields = ('full_name', 'email', 'translations__role')
    readonly_fields = ('first_name', 'last_name', 'slug', 'profile_picture_preview')
    fieldsets = (
        ('Informações Principais', {'fields': ('full_name', 'email', 'slug', ('profile_picture', 'profile_picture_preview'))}),
        ('Conteúdo (Traduzível)', {'fields': ('role', 'bio')}),
        ('Redes Sociais', {'fields': ('linkedin_url', 'instagram_url', 'whatsapp_number')}),
        ('Configurações', {'fields': ('is_team_member',)}),
    )

    @admin.display(description='Miniatura')
    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return format_html(f'<img src="{obj.profile_picture.url}" style="height: 50px; width: 50px; object-fit: cover; border-radius: 50%;" />')
        return "Sem Foto"

    @admin.display(description='Posts')
    def view_posts_link(self, obj):
        count = obj.posts.count()
        if count == 0:
            return "Nenhum"
        url = reverse("custom_admin:blog_post_changelist") + "?" + urlencode({"author__id": obj.id})
        return format_html('<a href="{}" target="_blank">Ver {} post(s)</a>', url, count)

@admin.register(Category, site=site)
class CategoryAdmin(TranslatableAdmin):
    list_display = ('name', 'slug', 'color_display', 'color', 'image_preview', 'post_count')
    list_editable = ('color',)
    search_fields = ('translations__name',)
    readonly_fields = ('image_preview',)
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'color', ('image', 'image_preview'))}),
    )

    def get_prepopulated_fields(self, request, obj=None):
        return {'slug': ('name',)}
    


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(posts_count=Count('posts'))

    @admin.display(description='Nº de Posts', ordering='posts_count')
    def post_count(self, obj):
        return obj.posts_count

    @admin.display(description='Cor')
    def color_display(self, obj):
        return format_html(f'<div style="background-color: {obj.color or "#fff"}; width: 25px; height: 25px; border-radius: 5px; border: 1px solid #ccc;"></div>')
     
    @admin.display(description='Miniatura')
    def image_preview(self, obj):
        if obj.image and hasattr(obj.image, 'url'):
            return format_html(f'<img src="{obj.image.url}" style="height: 50px; width: auto; border-radius: 5px;" />')
        return "Sem Imagem"

@admin.register(Post, site=site)
class PostAdmin(SortableAdminMixin, TranslatableAdmin):
    ordering = ['order']
    list_display = ('order', 'title', 'status', 'author', 'category', 'formatted_created_at', 'thumbnail_preview')
    list_editable = ('status', 'author', 'category')
    list_filter = ('status', 'created_at', 'author', 'category')
    search_fields = ('translations__title', 'translations__content')
    date_hierarchy = 'created_at'
    list_per_page = 15
    actions = ['make_published', 'make_draft', 'translate_selected']
    readonly_fields = ('created_at', 'updated_at', 'thumbnail_preview')
    fieldsets = (
        ('Conteúdo Principal', {'fields': ('title', 'slug', 'content')}),
        ('Organização e Mídia', {'fields': ('author', 'category', ('thumbnail', 'thumbnail_preview'))}),
        ('Publicação', {'fields': ('status', 'created_at', 'updated_at')}),
        ('SEO', {'fields': ('meta_title', 'meta_description')}),
        ('Palavras-chave', {
            'fields': ('keywords',),
            'description': 'Geradas automaticamente pelo pipeline IA. Edite se necessário.',
            'classes': ('collapse',),
        }),
    )

    def get_available_languages(self, obj):
        return ['pt-br']

    def get_language_tabs(self, request, obj, available_languages, css_class=None):
        # Passa apenas pt-br para o método pai → só uma aba é renderizada
        return super().get_language_tabs(request, obj, ['pt-br'], css_class)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .admin_views import auto_translate_post
        auto_translate_post(obj)

    @admin.action(description='Traduzir selecionados para EN / ES / FR (IA)')
    def translate_selected(self, request, queryset):
        from .admin_views import auto_translate_post
        count = queryset.count()
        for post in queryset:
            auto_translate_post(post)
        self.message_user(
            request,
            f"{count} post(s) enviado(s) para tradução em background. "
            "Atualize a página em alguns minutos para ver o resultado.",
            messages.SUCCESS,
        )

    def get_prepopulated_fields(self, request, obj=None):
        return {'slug': ('title',)}



    @admin.display(description='Criado em', ordering='created_at')
    def formatted_created_at(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%y')
        return "-"

    @admin.display(description='Miniatura')
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(f'<img src="{obj.thumbnail.url}" style="height: 60px; width: auto; border-radius: 5px;" />')
        return "Sem Imagem"

    @admin.action(description='Marcar selecionados como Publicado')
    def make_published(self, request, queryset):
        queryset.update(status='published')
        self.message_user(request, "Os posts selecionados foram publicados com sucesso.")
     
    @admin.action(description='Marcar selecionados como Rascunho')
    def make_draft(self, request, queryset):
        queryset.update(status='draft')
        self.message_user(request, "Os posts selecionados foram movidos para rascunho.")

@admin.register(AboutPage, site=site)
class AboutPageAdmin(TranslatableAdmin):
    readonly_fields = ('header_image_preview',)
    fieldsets = (
        ('Conteúdo da Página (Traduzível)', {'fields': ('title', 'content')}),
        ('Mídia', {'fields': ('header_image', 'header_image_preview')}),
    )
    @admin.display(description='Pré-visualização')
    def header_image_preview(self, obj):
        if obj.header_image:
            return format_html(f'<img src="{obj.header_image.url}" style="max-height: 200px; width: auto; border-radius: 5px;" />')
        return "Sem Imagem"
    def has_add_permission(self, request): return self.model.objects.count() == 0
    def has_delete_permission(self, request, obj=None): return False

@admin.register(ContactSubmission, site=site)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'submitted_at')
    readonly_fields = [f.name for f in ContactSubmission._meta.fields]
    list_filter = ('submitted_at',)
    search_fields = ('name', 'email', 'message')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

@admin.register(NewsletterSubscriber, site=site)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'subscribed_at')
    readonly_fields = ('email', 'subscribed_at')
    search_fields = ('email',)
    list_filter = ('subscribed_at',)
    def has_add_permission(self, request): return False

site.register(User, BaseUserAdmin)
site.register(Group, BaseGroupAdmin)