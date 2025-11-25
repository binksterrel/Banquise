"""
URL configuration for Banquise project.
"""
from django.contrib import admin
from django.urls import path, include
from scoring import views as scoring_views

urlpatterns = [
    # Routes admin custom avant l'admin Django pour éviter le catch-all
    path('admin/manage/', scoring_views.admin_manage, name='admin_manage_alt'),
    path('admin/credits/', scoring_views.admin_manage_credits, name='admin_manage_credits_alt'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')), 
    path('', include('scoring.urls')),
]

handler404 = 'scoring.views.custom_404'
handler200 = 'scoring.views.custom_200'
