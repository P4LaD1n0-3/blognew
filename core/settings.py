# core/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
# Adicionado para as strings de tradução
from django.utils.translation import gettext_lazy as _


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv(os.path.join(BASE_DIR, '.env'))


# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = [h for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h]
CSRF_TRUSTED_ORIGINS = [h for h in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if h]


# --- CHAVES DE API PARA SERVIÇOS EXTERNOS ---
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
GOOGLE_ADSENSE_PUB_ID = os.getenv('GOOGLE_ADSENSE_PUB_ID', '')
CREATOR_LINKEDIN_URL = os.getenv('CREATOR_LINKEDIN_URL', '')

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'blog.apps.BlogConfig',
    'dashboard',
    'tinymce',
    'adminsortable2',
    'parler',
]

LOGIN_URL = '/painel/login/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'core.middleware.AdminAnywhereMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

X_FRAME_OPTIONS = 'SAMEORIGIN'

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'blog.context_processors.site_settings_processor',
                'core.context_processors.settings_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.config(
            default=os.getenv('DATABASE_URL'),
            conn_max_age=600,
            ssl_require=True
        )
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Configuração de Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
CONTACT_EMAIL = os.getenv('CONTACT_EMAIL')


# --- CONFIGURAÇÃO DE INTERNACIONALIZAÇÃO (I18N) E PARLER ---
LANGUAGE_CODE = 'pt-br'

LANGUAGES = [
    ('pt-br', _('Português (Brasil)')),
    ('en', _('Inglês')),
    ('es', _('Espanhol')),
    ('fr', _('Francês')),
]

PARLER_LANGUAGES = {
    None: (
        {'code': 'pt-br', 'name': 'Português (Brasil)'},
        {'code': 'en', 'name': 'Inglês'},
        {'code': 'es', 'name': 'Espanhol'},
        {'code': 'fr', 'name': 'Francês'},
    ),
    'default': {
        'fallback': 'pt-br',  # idioma padrão
        'hide_untranslated': False,
    }
}



LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# --- CORREÇÃO DEFINITIVA APLICADA AQUI ---
# Este bloco é essencial para o funcionamento correto do site multilíngue.


TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
# --- FIM DA CONFIGURAÇÃO DE I18N E PARLER ---


# Static files
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DATA_UPLOAD_MAX_MEMORY_SIZE = 20971520 # 20MB
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# TinyMCE Configuration
TINYMCE_DEFAULT_CONFIG = {
    "height": "650px",
    "width": "100%",
    "menubar": True,
    "language": "pt_BR",

    "plugins":
        "advlist autolink lists link image charmap preview anchor "
        "searchreplace visualblocks code fullscreen insertdatetime media table "
        "help wordcount",

    "toolbar":
        "undo redo | formatselect | bold italic underline | "
        "alignleft aligncenter alignright alignjustify | "
        "bullist numlist outdent indent | link image media | removeformat | help", # ✅ A VÍRGULA AQUI É ESSENCIAL

    # Esta linha agora será lida corretamente, prevenindo o erro em novos posts.
    "entity_encoding": "raw",

    "content_style": "body { font-size: 18px; line-height: 1.6; font-family: 'Inter', 'Google Sans', sans-serif; color: #333; }",
    "content_css": "default",
    "skin": "oxide",
}


ADMINSORTABLE2_USE_STATIC_JQUERY = True

# Jazzmin Configuration
JAZZMIN_SETTINGS = {
    "custom_admin_site": "blog.admin.site", "welcome_sign": "Bem-vindo ao Painel Administrativo",
    "copyright": "Minimal News Ltd.", "search_model": ["blog.Post", "blog.Author"], "theme": "litera",
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Ver Site", "url": "blog:home", "new_window": True, "icon": "fas fa-globe"},
        {"app": "blog"}, {"model": "auth.User"},
    ],
    "show_sidebar": True, "navigation_expanded": True, "hide_apps": [], "hide_models": [],
    "order_with_respect_to": [
        "blog.SiteSettings", "blog.Author", "blog.AboutPage", "blog.Category",
        "blog.Post", "blog.ContactSubmission", "blog.NewsletterSubscriber", "auth",
    ],
    "custom_links": {
        "blog": [
            {
                "name": "IA Escritor",
                "url": "custom_admin:ai_writer",
                "icon": "fas fa-magic",
                "permissions": ["blog.add_post"],
            },
            {
                "name": "Configurações de IA",
                "url": "custom_admin:ai_settings",
                "icon": "fas fa-brain",
                "permissions": ["blog.change_sitesettings"],
            },
        ]
    },
    "icons": {
        "auth": "fas fa-user-shield", "auth.user": "fas fa-user-circle", "auth.Group": "fas fa-user-friends",
        "blog.SiteSettings": "fas fa-sliders-h", "blog.AboutPage": "fas fa-address-card",
        "blog.ContactSubmission": "fas fa-inbox", "blog.Author": "fas fa-user-astronaut",
        "blog.Category": "fas fa-layer-group", "blog.Post": "fas fa-file-alt",
        "blog.NewsletterSubscriber": "fas fa-paper-plane",
    },
    "default_icon_parents": "fas fa-chevron-circle-right", "default_icon_children": "fas fa-circle",
    "related_modal_active": False, "custom_css": None, "custom_js": None,
    "show_ui_builder": False, "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {"auth.user": "collapsible", "auth.group": "vertical_tabs"},
}



# ==============================================================================
# CONFIGURAÇÕES DE SEGURANÇA PARA PRODUÇÃO (HTTPS)
# ==============================================================================
# Estas configurações só devem ser ativadas em produção com um certificado SSL.


if DEBUG:
    WHITENOISE_AUTOREFRESH = True

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'



# ==============================================================================
# CONFIGURAÇÃO DE LOGGING PARA PRODUÇÃO
# ==============================================================================
# Este bloco irá capturar os erros que acontecem com DEBUG=False e imprimi-los
# nos logs do EasyPanel, para que possamos diagnosticar o problema.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': ('%(asctime)s [%(levelname)s] [%(name)s:%(lineno)s] '
                       '%(message)s'),
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        '': { # Logger raiz, captura tudo
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}