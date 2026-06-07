# blog/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from .models import ContactSubmission, NewsletterSubscriber

class SearchForm(forms.Form):
    """
    Formulário para a funcionalidade de busca no site.
    """
    query = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={
            'class': 'flex-grow px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-transparent transition',
            'placeholder': _('Buscar artigos...')
        })
    )

class ContactForm(forms.ModelForm):
    """
    Formulário para a seção de contato, baseado no modelo ContactSubmission.
    """
    class Meta:
        model = ContactSubmission
        fields = ['name', 'email', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': _('Seu nome completo'),
                'class': 'form-input'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': _('Seu melhor e-mail'),
                'class': 'form-input'
            }),
            'message': forms.Textarea(attrs={
                'placeholder': _('Sua mensagem...'),
                'class': 'form-textarea',
                'rows': 5
            }),
        }

class NewsletterSubscriptionForm(forms.ModelForm):
    """
    Formulário para a inscrição na newsletter, baseado no modelo NewsletterSubscriber.
    """
    class Meta:
        model = NewsletterSubscriber
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': _('Digite seu melhor e-mail'),
                'class': 'newsletter-input',
                'aria-label': _('Endereço de e-mail para newsletter'),
            })
        }
