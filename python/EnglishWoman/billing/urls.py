from django.urls import path
from . import views

urlpatterns = [
    path('plans/', views.plans_page, name='plans'),
    path('pay/<str:plan_key>/', views.start_payment, name='start_payment'),
    path('callback/', views.payment_callback, name='payment_callback'),
]
