from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib.sitemaps.views import sitemap
from django.views.generic.base import TemplateView
from django.urls import path, include, re_path
from django.views.static import serve
from blog.admin import site as custom_admin_site
from blog.sitemaps import PostSitemap, CategorySitemap, StaticViewSitemap
from blog.views import root_redirect_view
#from blog.views import ads_txt # Supondo que a view está no app 'blog'



sitemaps = {
    'posts': PostSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
}

urlpatterns = [
    path('', root_redirect_view, name='root_redirect'),
    path('painel/', include('dashboard.urls')),
    path('tinymce/', include('tinymce.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
]

urlpatterns += i18n_patterns(
    path('admin/', custom_admin_site.urls),
    path('', include('blog.urls', namespace='blog')),
)

#path('ads.txt', ads_txt, name='ads_txt'),


handler404 = 'blog.views.custom_page_not_found_view'

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]