# blog/urls.py

from django.urls import path
from .views import (
    HomePageView,
    NewsletterSubscribeView,
    PostListView,
    PostDetailView,
    CategoryListView,
    PostsByCategoryView,
    SearchView,
    AboutPageView,
    AuthorDetailView,
)

app_name = 'blog'

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('artigos/', PostListView.as_view(), name='post_list'),
    path('busca/', SearchView.as_view(), name='search'),
    path('categorias/', CategoryListView.as_view(), name='category_list'),
    path('sobre/', AboutPageView.as_view(), name='about'),
    path('assinar-newsletter/', NewsletterSubscribeView.as_view(), name='newsletter_subscribe'),
    path('categoria/<slug:slug>/', PostsByCategoryView.as_view(), name='posts_by_category'),
    path('autor/<slug:slug>/<int:pk>/', AuthorDetailView.as_view(), name='author_detail'),
    path('<slug:category_slug>/<slug:post_slug>/', PostDetailView.as_view(), name='post_detail'),
]