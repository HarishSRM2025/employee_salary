from django.contrib import admin

from .models import EmployeeSalary


@admin.register(EmployeeSalary)
class EmployeeSalaryAdmin(admin.ModelAdmin):
    list_display = (
        'employee_name',
        'employee_id',
        'tenant_id',
        'month',
        'year',
        'base_salary',
        'net_salary',
        'status',
    )
    list_filter = ('tenant_id', 'year', 'month', 'status')
    search_fields = ('employee_name', 'employee_id', 'tenant_id')
    readonly_fields = ('calculated_at', 'updated_at')
