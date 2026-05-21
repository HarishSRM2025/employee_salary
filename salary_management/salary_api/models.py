from django.db import models

class EmployeeSalary(models.Model):
    STATUS_CHOICES = [
        ('Calculated', 'Calculated'),
        ('Paid', 'Paid'),
        ('Cancelled', 'Cancelled'),
    ]

    tenant_id = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=100)
    employee_name = models.CharField(max_length=100)
    month = models.IntegerField()  # 1 to 12
    year = models.IntegerField()
    base_salary = models.FloatField()
    worked_days = models.IntegerField()
    lop_days = models.IntegerField()
    total_days = models.IntegerField()
    deductions = models.FloatField()
    net_salary = models.FloatField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Calculated')
    calculated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month', 'employee_name']
        unique_together = ('tenant_id', 'employee_id', 'month', 'year')

    def __str__(self):
        return f"{self.employee_name} - {self.month}/{self.year} - {self.net_salary}"
