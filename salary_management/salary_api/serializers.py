from rest_framework import serializers
from .models import EmployeeSalary

class EmployeeSalarySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeSalary
        fields = '__all__'
