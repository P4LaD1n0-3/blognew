# blog/sitemaps.py
from django.contrib.sitemaps import Sitemap
from .models import Post, Category
from django.urls import reverse

class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Post.objects.filter(status='published')

    def lastmod(self, obj):
        return obj.updated_at

class CategorySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Category.objects.all()

# Adicione outras páginas estáticas se desejar
class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return ['blog:home', 'blog:about', 'blog:category_list']

    def location(self, item):
        return reverse(item)