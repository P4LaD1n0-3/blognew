# blog/views.py

from django.db.models import Q, Count
from django.views.generic import ListView, DetailView, TemplateView, View
from django.views.generic.edit import FormMixin
from django.urls import reverse_lazy, reverse  # ✅ Adicionado 'reverse' para o redirecionamento
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render
from django.http import Http404
from .models import AboutPage, Post, Category, Author, SiteSettings
from .forms import SearchForm, ContactForm, NewsletterSubscriptionForm

class HomePageView(FormMixin, TemplateView):
    """
    View para a página inicial (index.html), agora com envio de e-mail.
    """
    template_name = 'blog/index.html'
    form_class = ContactForm
    success_url = reverse_lazy('blog:home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        all_published_posts = Post.objects.filter(status='published').select_related('author', 'category').order_by('order')

        featured_post = all_published_posts.first()
        context['featured_post'] = featured_post
        
        if featured_post:
            remaining_posts = all_published_posts.exclude(pk=featured_post.pk)
        else:
            remaining_posts = all_published_posts
            
        site_settings = SiteSettings.objects.translated().first() or SiteSettings.load()
        num_posts_to_display = site_settings.posts_in_home_grid if site_settings else 8
        context['latest_posts'] = remaining_posts[:num_posts_to_display]
        
        context['search_form'] = SearchForm()
        context['newsletter_form'] = NewsletterSubscriptionForm()
        
        context['carousel_categories'] = Category.objects.annotate(
            num_posts=Count('posts', filter=Q(posts__status='published'))
        ).order_by('-num_posts')[:8]

        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            form.save() 
            try:
                nome = form.cleaned_data['name']
                email_cliente = form.cleaned_data['email']
                mensagem = form.cleaned_data['message']
                subject = f"Nova Mensagem do Site de: {nome}"
                message_body = f"Você recebeu uma nova mensagem de contato.\n\nNome: {nome}\nE-mail: {email_cliente}\nMensagem:\n{mensagem}"
                send_mail(
                    subject, message_body, settings.EMAIL_HOST_USER,
                    [settings.CONTACT_EMAIL], fail_silently=False,
                )
                messages.success(request, 'Sua mensagem foi enviada com sucesso!', extra_tags='contact')
            except Exception as e:
                messages.warning(request, 'Sua mensagem foi registrada, mas ocorreu um erro ao enviar a notificação.', extra_tags='contact')
            return self.form_valid(form)
        else:
            messages.error(request, 'Ocorreu um erro. Por favor, verifique os campos.', extra_tags='contact')
            return self.form_invalid(form)

    def get_success_url(self):
        return f"{super().get_success_url()}#contact-section"


class NewsletterSubscribeView(View):
    def post(self, request, *args, **kwargs):
        form = NewsletterSubscriptionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Obrigado por se inscrever!', extra_tags='newsletter')
        else:
            error_message = form.errors.get('email', ['Ocorreu um erro. Por favor, tente novamente.'])[0]
            messages.error(request, error_message, extra_tags='newsletter')
        
        referer_url = request.META.get('HTTP_REFERER', reverse_lazy('blog:home'))
        return redirect(f"{referer_url.split('#')[0]}#newsletter-section")


class PostListView(ListView):
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 9

    def get_queryset(self):
        return Post.objects.filter(status='published').select_related('author', 'category').order_by('order')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = SearchForm()
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'

    def get_object(self, queryset=None):
        category_slug = self.kwargs.get('category_slug')
        post_slug = self.kwargs.get('post_slug')

        if not category_slug or not post_slug:
            raise Http404("URL inválida. Slug da categoria ou do post ausente.")

        queryset = self.get_queryset().select_related('author', 'category')

        filters = {
            'translations__slug': post_slug,
            'category__translations__slug': category_slug,
        }
        # Rascunhos só são visíveis para staff/superuser autenticados (preview)
        user = self.request.user
        if not (user.is_authenticated and (user.is_staff or user.is_superuser)):
            filters['status'] = 'published'

        post_obj = get_object_or_404(queryset, **filters)
        return post_obj

    def get_queryset(self):
        return Post.objects.all()

    _PT_STOPWORDS = {
        'de','da','do','e','o','a','os','as','em','no','na','por','um','uma',
        'que','se','ao','com','para','sua','seu','seus','suas','como','mas',
        'mais','foi','é','não','ou','são','esta','este','isso','ele','ela',
        'eles','nas','nos','pelo','pela','entre','sobre','isso','aqui',
        'quando','então','também','muito','até','já','após','sua',
    }

    def _get_related_posts(self, current_post, limit=4):
        def title_words(post):
            return set(post.title.lower().split()) - self._PT_STOPWORDS

        def kw_set(post):
            if not getattr(post, 'keywords', ''):
                return set()
            return {k.strip().lower() for k in post.keywords.split(',') if k.strip()}

        curr_words = title_words(current_post)
        curr_kws   = kw_set(current_post)

        candidates = (
            Post.objects.filter(status='published')
            .exclude(pk=current_post.pk)
            .select_related('author', 'category')
        )

        scored = []
        for post in candidates:
            title_overlap = len(curr_words & title_words(post))
            kw_overlap    = len(curr_kws  & kw_set(post)) * 3
            cat_bonus     = 2 if post.category_id == current_post.category_id else 0
            score = title_overlap + kw_overlap + cat_bonus
            if score > 0:
                scored.append((score, post.created_at, post))

        scored.sort(key=lambda x: (-x[0], -x[1].timestamp()))
        return [p for _, _, p in scored[:limit]]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_post = self.object
        context['related_posts'] = self._get_related_posts(current_post)
        context['search_form'] = SearchForm()
        return context


class CategoryListView(ListView):
    model = Category
    template_name = 'blog/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        queryset = Category.objects.annotate(
            num_posts=Count('posts', filter=Q(posts__status='published'))
        ).distinct()
        return queryset.order_by('id')
    

class PostsByCategoryView(ListView):
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 9

    def get_queryset(self):
        self.category = get_object_or_404(Category, translations__slug=self.kwargs['slug'])
        return Post.objects.filter(
            category=self.category, status='published'
        ).select_related('author', 'category').order_by('order')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Artigos na Categoria: {self.category.name}'
        context['search_form'] = SearchForm()
        context['category'] = self.category
        return context


class SearchView(ListView):
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 9

    def get_queryset(self):
        form = SearchForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            return Post.objects.translated().filter(
                Q(translations__title__icontains=query) | 
                Q(translations__content__icontains=query) |
                Q(category__translations__name__icontains=query),
                status='published'
            ).select_related('author', 'category').distinct().order_by('order')
        return Post.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('query', '')
        context['page_title'] = f'Resultados da busca por: "{query}"'
        context['search_form'] = SearchForm(self.request.GET)
        context['query'] = query
        return context


class AboutPageView(TemplateView):
    template_name = 'blog/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = AboutPage.objects.translated().first()
        context['team_members'] = Author.objects.translated().filter(is_team_member=True)
        return context
    

class AuthorDetailView(DetailView):
    model = Author
    template_name = 'blog/author_detail.html'
    context_object_name = 'author'
    slug_field = 'slug'

    def get_queryset(self):
        return Author.objects.translated()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author = self.get_object()
        context['posts'] = Post.objects.filter(
            author=author, status='published'
        ).select_related('category').order_by('order')
        return context


def custom_page_not_found_view(request, exception):
    # ✅ CORREÇÃO APLICADA: Adicionamos o contexto mínimo necessário (search_form)
    # para que o template base (e o cabeçalho) possa ser renderizado sem quebrar.
    # Também corrigi o nome do template de um erro de digitação.
    context = {
        'search_form': SearchForm(),
    }
    return render(request, "blog/404.html", context, status=404)


# ✅ NOVA VIEW ADICIONADA: Esta view irá redirecionar a URL raiz para a home.
def root_redirect_view(request):
    """
    Redireciona a URL raiz (/) para a página inicial com o prefixo do idioma padrão.
    """
    return redirect(reverse('blog:home'))