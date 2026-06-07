from django import forms
from parler.forms import TranslatableModelForm, TranslatedField
from tinymce.widgets import TinyMCE
from blog.models import Post, Author, Category, SiteSettings, AboutPage


class PostForm(TranslatableModelForm):
    content = TranslatedField(
        form_class=forms.CharField,
        widget=TinyMCE(attrs={'cols': 80, 'rows': 30}),
        required=False,
    )

    class Meta:
        model = Post
        fields = [
            'title', 'slug', 'content', 'meta_title', 'meta_description',
            'author', 'category', 'thumbnail', 'keywords', 'status',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'Título do post',
                'id': 'id_title',
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'gerado-automaticamente',
                'id': 'id_slug',
            }),
            'meta_title': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'maxlength': '60',
                'placeholder': 'Máx. 60 caracteres',
            }),
            'meta_description': forms.Textarea(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'rows': 3,
                'maxlength': '160',
                'placeholder': 'Máx. 160 caracteres',
            }),
            'keywords': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'palavra1, palavra2, palavra3',
            }),
            'status': forms.Select(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
            }),
            'author': forms.Select(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
            }),
            'category': forms.Select(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
            }),
            'thumbnail': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
            }),
        }


class AuthorForm(TranslatableModelForm):
    class Meta:
        model = Author
        fields = [
            'full_name', 'email', 'role', 'bio',
            'profile_picture', 'linkedin_url', 'instagram_url',
            'whatsapp_number', 'is_team_member',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'Nome completo',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'email@exemplo.com',
            }),
            'role': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'Ex: Editor-Chefe',
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'rows': 4,
                'placeholder': 'Biografia do autor...',
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'https://linkedin.com/in/...',
            }),
            'instagram_url': forms.URLInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'https://instagram.com/...',
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': '5511999999999',
            }),
            'profile_picture': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
            }),
            'is_team_member': forms.CheckboxInput(attrs={
                'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500',
            }),
        }


class CategoryForm(TranslatableModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'image', 'color']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'Nome da categoria',
                'id': 'id_cat_name',
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'gerado-automaticamente',
                'id': 'id_cat_slug',
            }),
            'color': forms.Select(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
            }),
        }


class SiteSettingsForm(TranslatableModelForm):
    groq_api_key = forms.CharField(
        required=False,
        label='Chave API Groq',
        widget=forms.PasswordInput(render_value=True, attrs={
            'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none font-mono',
            'placeholder': 'gsk_...',
            'autocomplete': 'off',
        }),
    )

    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'instagram_url', 'linkedin_url',
            'whatsapp_number', 'posts_in_home_grid',
            'favicon', 'logo', 'show_name_with_logo', 'groq_api_key',
        ]
        widgets = {
            'site_name': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
            }),
            'instagram_url': forms.URLInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'https://instagram.com/...',
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'https://linkedin.com/in/...',
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': '5511999999999',
            }),
            'posts_in_home_grid': forms.NumberInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'min': 1, 'max': 50,
            }),
            'favicon': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
            }),
            'logo': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
            }),
            'show_name_with_logo': forms.CheckboxInput(attrs={
                'class': 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500',
            }),
        }


class AboutPageForm(TranslatableModelForm):
    content = TranslatedField(
        form_class=forms.CharField,
        widget=TinyMCE(attrs={'cols': 80, 'rows': 30}),
        required=False,
    )

    class Meta:
        model = AboutPage
        fields = ['title', 'content', 'header_image']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none',
                'placeholder': 'Título da página Sobre',
            }),
            'header_image': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-slate-500 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100',
            }),
        }
