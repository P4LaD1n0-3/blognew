import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage

from blog.models import (
    AboutPage, Author, Category, ContactSubmission,
    NewsletterSubscriber, Post, SiteSettings,
)
from .decorators import master_required
from .forms import (
    AboutPageForm, AuthorForm, CategoryForm, PostForm, SiteSettingsForm,
)

def log_dashboard_action(user, obj, action_flag, message=""):
    try:
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=str(obj),
            action_flag=action_flag,
            change_message=message
        )
    except Exception as e:
        print(f"[Dashboard Log] Erro ao registrar log: {e}")
from .forms import (
    AboutPageForm, AuthorForm, CategoryForm, PostForm, SiteSettingsForm,
)

LANG = 'pt-br'


# ─── Auth ──────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('dashboard:index')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user and (user.is_staff or user.is_superuser):
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next') or ''
            if next_url and next_url.startswith('/painel/'):
                return redirect(next_url)
            return redirect('dashboard:index')
        error = 'Credenciais inválidas ou acesso não autorizado.'
    return render(request, 'dashboard/login.html', {'error': error})


@require_POST
@master_required
def logout_view(request):
    logout(request)
    return redirect('dashboard:login')


# ─── Index ─────────────────────────────────────────────────────────────

@master_required
def index(request):
    context = {
        'total_posts': Post.objects.count(),
        'published_posts': Post.objects.filter(status='published').count(),
        'draft_posts': Post.objects.filter(status='draft').count(),
        'total_authors': Author.objects.count(),
        'total_contacts': ContactSubmission.objects.count(),
        'total_subscribers': NewsletterSubscriber.objects.count(),
        'total_categories': Category.objects.count(),
        'recent_posts': Post.objects.select_related('author', 'category').order_by('-created_at')[:6],
        'recent_contacts': ContactSubmission.objects.order_by('-submitted_at')[:5],
    }
    
    try:
        from django.contrib.admin.models import LogEntry
        context['recent_logs'] = LogEntry.objects.select_related('content_type', 'user').order_by('-action_time')[:10]
    except Exception:
        context['recent_logs'] = []
        
    return render(request, 'dashboard/index.html', context)


# ─── Posts ─────────────────────────────────────────────────────────────

@csrf_exempt
@master_required
@require_POST
def tinymce_upload_image(request):
    if 'file' in request.FILES:
        file = request.FILES['file']
        file_name = default_storage.save(f'uploads/{file.name}', file)
        url = default_storage.url(file_name)
        return JsonResponse({'location': url})
    return JsonResponse({'error': 'Nenhuma imagem enviada'}, status=400)


@master_required
def posts_list(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        selected = request.POST.getlist('selected_ids')
        if action == 'publish' and selected:
            count = Post.objects.filter(pk__in=selected).update(status='published')
            messages.success(request, f'{count} post(s) publicado(s).')
        elif action == 'draft' and selected:
            count = Post.objects.filter(pk__in=selected).update(status='draft')
            messages.success(request, f'{count} post(s) movido(s) para rascunho.')
        return redirect('dashboard:posts_list')

    qs = Post.objects.select_related('author', 'category').order_by('order', '-created_at')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(translations__title__icontains=q).distinct()
    status_filter = request.GET.get('status', '')
    if status_filter in ('published', 'draft'):
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dashboard/posts_list.html', {
        'page_obj': page_obj,
        'search_q': q,
        'status_filter': status_filter,
        'all_authors': Author.objects.all(),
        'all_categories': Category.objects.all(),
    })


@master_required
@require_POST
def post_quick_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    try:
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')
        
        from django.contrib.admin.models import CHANGE
        if field == 'status' and value in ['published', 'draft']:
            post.status = value
            post.save(update_fields=['status'])
            log_dashboard_action(request.user, post, CHANGE, "Editou status rapidamente")
        elif field == 'category':
            cat = Category.objects.get(pk=value) if value else None
            post.category = cat
            post.save(update_fields=['category'])
            log_dashboard_action(request.user, post, CHANGE, "Editou categoria rapidamente")
        elif field == 'author':
            auth = Author.objects.get(pk=value) if value else None
            post.author = auth
            post.save(update_fields=['author'])
            log_dashboard_action(request.user, post, CHANGE, "Editou autor rapidamente")
            
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@master_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        form.language_code = LANG
        if form.is_valid():
            post = form.save(commit=False)
            post.set_current_language(LANG)
            post.save()
            _trigger_translation(post)
            
            from django.contrib.admin.models import ADDITION
            log_dashboard_action(request.user, post, ADDITION, "Criou post")
            
            messages.success(request, 'Post criado com sucesso.')
            return redirect('dashboard:posts_list')
    else:
        form = PostForm()
        form.language_code = LANG
    return render(request, 'dashboard/posts_form.html', {'form': form, 'post': None})


@master_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.set_current_language(LANG)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        form.language_code = LANG
        if form.is_valid():
            form.save()
            _trigger_translation(post)
            
            from django.contrib.admin.models import CHANGE
            log_dashboard_action(request.user, post, CHANGE, "Editou post")
            
            messages.success(request, 'Post atualizado com sucesso.')
            return redirect('dashboard:posts_list')
    else:
        form = PostForm(instance=post)
        form.language_code = LANG
    return render(request, 'dashboard/posts_form.html', {'form': form, 'post': post})


@master_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    title = post.safe_translation_getter('title', any_language=True) or f'Post #{pk}'
    
    from django.contrib.admin.models import DELETION
    log_dashboard_action(request.user, post, DELETION, "Excluiu post")
    
    post.delete()
    messages.success(request, f'"{title}" excluído com sucesso.')
    return redirect('dashboard:posts_list')


@master_required
@require_POST
def posts_reorder(request):
    try:
        data = json.loads(request.body)
        for item in data:
            Post.objects.filter(pk=item['id']).update(order=item['order'])
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


# ─── Authors ───────────────────────────────────────────────────────────

@master_required
def authors_list(request):
    qs = Author.objects.order_by('full_name')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(full_name__icontains=q)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dashboard/authors_list.html', {'page_obj': page_obj, 'search_q': q})


@master_required
def author_create(request):
    if request.method == 'POST':
        form = AuthorForm(request.POST, request.FILES)
        form.language_code = LANG
        if form.is_valid():
            author = form.save(commit=False)
            author.set_current_language(LANG)
            author.save()
            
            from django.contrib.admin.models import ADDITION
            log_dashboard_action(request.user, author, ADDITION, "Criou autor")
            
            messages.success(request, 'Autor criado com sucesso.')
            return redirect('dashboard:authors_list')
    else:
        form = AuthorForm()
        form.language_code = LANG
    return render(request, 'dashboard/authors_form.html', {'form': form, 'author': None})


@master_required
def author_edit(request, pk):
    author = get_object_or_404(Author, pk=pk)
    author.set_current_language(LANG)
    if request.method == 'POST':
        form = AuthorForm(request.POST, request.FILES, instance=author)
        form.language_code = LANG
        if form.is_valid():
            form.save()
            
            from django.contrib.admin.models import CHANGE
            log_dashboard_action(request.user, author, CHANGE, "Editou autor")
            
            messages.success(request, 'Autor atualizado com sucesso.')
            return redirect('dashboard:authors_list')
    else:
        form = AuthorForm(instance=author)
        form.language_code = LANG
    return render(request, 'dashboard/authors_form.html', {'form': form, 'author': author})


@master_required
@require_POST
def author_delete(request, pk):
    author = get_object_or_404(Author, pk=pk)
    name = author.full_name
    
    from django.contrib.admin.models import DELETION
    log_dashboard_action(request.user, author, DELETION, "Excluiu autor")
    
    author.delete()
    messages.success(request, f'"{name}" excluído com sucesso.')
    return redirect('dashboard:authors_list')


# ─── Categories ────────────────────────────────────────────────────────

@master_required
def categories_list(request):
    qs = Category.objects.order_by('pk')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dashboard/categories_list.html', {'page_obj': page_obj})


@master_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        form.language_code = LANG
        if form.is_valid():
            cat = form.save(commit=False)
            cat.set_current_language(LANG)
            try:
                cat.save()
                
                from django.contrib.admin.models import ADDITION
                log_dashboard_action(request.user, cat, ADDITION, "Criou categoria")
                
                messages.success(request, 'Categoria criada com sucesso.')
                return redirect('dashboard:categories_list')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {e}')
    else:
        form = CategoryForm()
        form.language_code = LANG
    return render(request, 'dashboard/categories_form.html', {'form': form, 'category': None})


@master_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.set_current_language(LANG)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        form.language_code = LANG
        if form.is_valid():
            try:
                form.save()
                
                from django.contrib.admin.models import CHANGE
                log_dashboard_action(request.user, category, CHANGE, "Editou categoria")
                
                messages.success(request, 'Categoria atualizada com sucesso.')
                return redirect('dashboard:categories_list')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {e}')
    else:
        form = CategoryForm(instance=category)
        form.language_code = LANG
    return render(request, 'dashboard/categories_form.html', {'form': form, 'category': category})


@master_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    name = category.safe_translation_getter('name', any_language=True) or f'Categoria #{pk}'
    try:
        from django.contrib.admin.models import DELETION
        log_dashboard_action(request.user, category, DELETION, "Excluiu categoria")
        
        category.delete()
        messages.success(request, f'"{name}" excluída com sucesso.')
    except Exception as e:
        messages.error(request, f'Não foi possível excluir: {e}')
    return redirect('dashboard:categories_list')


# ─── Site Settings ─────────────────────────────────────────────────────

@master_required
def site_settings(request):
    instance = SiteSettings.load()
    instance.set_current_language(LANG)
    if request.method == 'POST':
        form = SiteSettingsForm(request.POST, request.FILES, instance=instance)
        form.language_code = LANG
        if form.is_valid():
            form.save()
            messages.success(request, 'Configurações salvas com sucesso.')
            return redirect('dashboard:site_settings')
    else:
        form = SiteSettingsForm(instance=instance)
        form.language_code = LANG
    return render(request, 'dashboard/site_settings.html', {'form': form, 'instance': instance})


# ─── About Page ────────────────────────────────────────────────────────

@master_required
def about_page(request):
    instance = AboutPage.objects.first()
    if instance:
        instance.set_current_language(LANG)
    if request.method == 'POST':
        form = AboutPageForm(request.POST, request.FILES, instance=instance)
        form.language_code = LANG
        if form.is_valid():
            about = form.save(commit=False)
            about.set_current_language(LANG)
            about.save()
            messages.success(request, 'Página Sobre atualizada com sucesso.')
            return redirect('dashboard:about')
    else:
        form = AboutPageForm(instance=instance)
        form.language_code = LANG
    return render(request, 'dashboard/about.html', {'form': form, 'instance': instance})


# ─── Contacts & Newsletter ─────────────────────────────────────────────

@master_required
def contacts_list(request):
    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        qs = ContactSubmission.objects.filter(
            Q(name__icontains=q) | Q(email__icontains=q)
        ).order_by('-submitted_at')
    else:
        qs = ContactSubmission.objects.order_by('-submitted_at')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dashboard/contacts.html', {'page_obj': page_obj, 'search_q': q})


@master_required
def newsletter_list(request):
    qs = NewsletterSubscriber.objects.order_by('-subscribed_at')
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'dashboard/newsletter.html', {'page_obj': page_obj})


# ─── AI Features ───────────────────────────────────────────────────────

@master_required
def ai_writer(request):
    from blog.admin_views import AgentPipeline
    site_settings = SiteSettings.load()
    default_api_key = site_settings.groq_api_key or ''

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'test_connection':
            key = request.POST.get('api_key', '').strip()
            if not key:
                return JsonResponse({'status': 'error', 'error': 'Insira uma chave API primeiro.'})
            try:
                pipeline = AgentPipeline('llama-3.3-70b-versatile', key)
                result = pipeline._call_llm(
                    'Você é um assistente de teste. Responda APENAS com: CONECTADO',
                    'ping',
                    expect_json=False,
                )
                snippet = str(result).strip()[:80]
                return JsonResponse({'status': 'success', 'message': f'Conexão OK: {snippet}'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'error': str(e)[:300]})

        if action == 'save_key':
            key = request.POST.get('api_key', '').strip()
            site_settings.groq_api_key = key
            site_settings.save()
            request.session['ai_writer_api_key'] = key
            return JsonResponse({'status': 'success', 'message': 'Chave API salva permanentemente!'})

    context = {
        'categories': Category.objects.all(),
        'authors': Author.objects.filter(is_team_member=True),
        'saved_provider': request.session.get('ai_writer_provider', 'llama-3.3-70b-versatile'),
        'saved_api_key': request.session.get('ai_writer_api_key') or default_api_key,
        'saved_category': request.session.get('ai_writer_category', ''),
        'saved_author': request.session.get('ai_writer_author', ''),
        'saved_prompt': request.session.get('ai_writer_prompt', ''),
        'saved_quantity': request.session.get('ai_writer_quantity', 1),
        'saved_generate_image': request.session.get('ai_writer_generate_image', True),
        'saved_publish_now': request.session.get('ai_writer_publish_now', False),
    }
    return render(request, 'dashboard/ai_writer.html', context)


@master_required
@require_POST
def ai_generate(request):
    from blog.admin_views import AgentPipeline, ImageEngine, auto_translate_post
    from django.utils.text import slugify
    from django.core.files.base import ContentFile

    provider = request.POST.get('provider', 'llama-3.3-70b-versatile')
    api_key = request.POST.get('api_key', '').strip()
    category_id = request.POST.get('category')
    author_id = request.POST.get('author')
    prompt = request.POST.get('prompt', '').strip()
    quantity_str = request.POST.get('quantity', '1')
    quantity = max(1, min(10, int(quantity_str) if quantity_str.isdigit() else 1))
    current_iteration = int(request.POST.get('current_iteration', '1'))
    generate_image = request.POST.get('generate_image') == '1'
    publish_now = request.POST.get('publish_now') == '1'

    if current_iteration == 1:
        request.session['ai_writer_provider'] = provider
        request.session['ai_writer_api_key'] = api_key
        request.session['ai_writer_category'] = category_id
        request.session['ai_writer_author'] = author_id
        request.session['ai_writer_prompt'] = prompt
        request.session['ai_writer_quantity'] = quantity
        request.session['ai_writer_generate_image'] = generate_image
        request.session['ai_writer_publish_now'] = publish_now

    if not api_key or not prompt or not category_id or not author_id:
        return JsonResponse({'status': 'error', 'error': 'Preencha todos os campos obrigatórios.'})

    try:
        category = Category.objects.get(id=category_id)
        author = Author.objects.get(id=author_id)
        model_name = provider
        i = current_iteration - 1

        pipeline = AgentPipeline(model_name, api_key)
        result = pipeline.run(prompt, variation=i + 1, total=quantity)

        post = Post()
        post.set_current_language(LANG)
        post.title = result['title']
        post.content = result['html']
        post.category = category
        post.author = author
        post.status = 'published' if publish_now else 'draft'
        post.meta_title = result.get('meta_title', '')
        post.meta_description = result.get('meta_description', '')
        post.keywords = result.get('keywords', '')

        if generate_image and result.get('cover_url'):
            try:
                img_bytes = ImageEngine.download(result['cover_url'])
                if img_bytes:
                    fname = f"{slugify(result['title'])[:30]}_cover.jpg"
                    post.thumbnail.save(fname, ContentFile(img_bytes), save=False)
            except Exception as e:
                print(f'[AI Cover] Erro: {e}')

        post.save()
        auto_translate_post(post)
        
        from django.contrib.admin.models import ADDITION
        log_dashboard_action(request.user, post, ADDITION, "Gerou post via IA")

        return JsonResponse({
            'status': 'success',
            'title': result['title'],
            'thoughts': result.get('thoughts', ''),
            'logs': result.get('logs', ''),
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)[:500]})


@master_required
@require_POST
def ai_format(request):
    from blog.admin_views import FormatContentView
    if not request.POST.get('api_key'):
        session_key = request.session.get('ai_writer_api_key', '')
        if session_key:
            post_data = request.POST.copy()
            post_data['api_key'] = session_key
            request.POST = post_data
    view = FormatContentView()
    return view.post(request)


@master_required
@require_POST
def ai_translate(request, post_id):
    from blog.admin_views import TranslatePostView
    request.POST = request.POST.copy()
    request.POST['post_id'] = str(post_id)
    view = TranslatePostView()
    return view.post(request)


@master_required
@require_POST
def ai_seo(request, post_id):
    from blog.admin_views import GenerateSEOView
    view = GenerateSEOView()
    return view.post(request)

# ─── Helper ────────────────────────────────────────────────────────────

def _trigger_translation(post):
    try:
        from blog.admin_views import auto_translate_post
        auto_translate_post(post)
    except Exception as e:
        print(f'[Dashboard] Translation trigger error: {e}')
