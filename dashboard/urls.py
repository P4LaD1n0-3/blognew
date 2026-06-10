from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('posts/', views.posts_list, name='posts_list'),
    path('posts/criar/', views.post_create, name='post_create'),
    path('posts/upload-image/', views.tinymce_upload_image, name='tinymce_upload_image'),
    path('posts/<int:pk>/editar/', views.post_edit, name='post_edit'),
    path('posts/<int:pk>/quick-edit/', views.post_quick_edit, name='post_quick_edit'),
    path('posts/<int:pk>/excluir/', views.post_delete, name='post_delete'),
    path('posts/ordenar/', views.posts_reorder, name='posts_reorder'),

    path('autores/', views.authors_list, name='authors_list'),
    path('autores/criar/', views.author_create, name='author_create'),
    path('autores/<int:pk>/editar/', views.author_edit, name='author_edit'),
    path('autores/<int:pk>/excluir/', views.author_delete, name='author_delete'),

    path('categorias/', views.categories_list, name='categories_list'),
    path('categorias/criar/', views.category_create, name='category_create'),
    path('categorias/<int:pk>/editar/', views.category_edit, name='category_edit'),
    path('categorias/<int:pk>/excluir/', views.category_delete, name='category_delete'),

    path('configuracoes/', views.site_settings, name='site_settings'),
    path('sobre/', views.about_page, name='about'),
    path('contatos/', views.contacts_list, name='contacts'),
    path('newsletter/', views.newsletter_list, name='newsletter'),

    path('ia/escritor/', views.ai_writer, name='ai_writer'),
    path('ia/gerar/', views.ai_generate, name='ai_generate'),
    path('ia/formatar/', views.ai_format, name='ai_format'),
    path('ia/traduzir/<int:post_id>/', views.ai_translate, name='ai_translate'),
    path('ia/seo/<int:post_id>/', views.ai_seo, name='ai_seo'),
]
