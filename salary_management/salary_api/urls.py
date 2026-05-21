from django.urls import path
from . import views

urlpatterns = [
    path('tenant/salary/calculate/', views.calculate_salary),
    path('tenant/salary/', views.salary_list),
    path('tenant/salary/<int:pk>/pay/', views.pay_salary),
    path('tenant/salary/<int:pk>/cancel/', views.cancel_salary),
    path('tenant/salary/<int:pk>/', views.delete_salary),
]
