import os
import calendar
import requests
from datetime import datetime, date
from django.shortcuts import render
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import EmployeeSalary
from .serializers import EmployeeSalarySerializer

@api_view(['POST'])
def calculate_salary(request):
    """
    Calculate and save/update the salary for a specific employee or all employees in a tenant
    for a given month and year.
    
    Payload:
    {
        "tenant_id": "T1",
        "employee_id": "EMP101", // Optional. If omitted, calculates for all tenant employees
        "month": 5,
        "year": 2026
    }
    """
    tenant_id = request.data.get('tenant_id')
    employee_id = request.data.get('employee_id')
    month_val = request.data.get('month')
    year_val = request.data.get('year')

    if tenant_id is not None:
        tenant_id = str(tenant_id)
    if employee_id is not None:
        employee_id = str(employee_id)

    if not tenant_id or not month_val or not year_val:
        return Response(
            {"error": "tenant_id, month, and year are required fields"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        month = int(month_val)
        year = int(year_val)
        if month < 1 or month > 12:
            raise ValueError()
    except ValueError:
        return Response(
            {"error": "month must be an integer between 1 and 12, and year must be a valid integer"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # 1. Calculate total days in target month
    total_days = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, total_days)

    emp_api_url = os.getenv('EMP_API', 'http://127.0.0.1:8000')

    # 2. Fetch employee details from employee_info service
    try:
        employees_response = requests.get(f"{emp_api_url}/api/tenant/employee_data/", timeout=5)
        if employees_response.status_code != 200:
            return Response(
                {"error": f"Failed to fetch employee details from employee service: {employees_response.text}"},
                status=status.HTTP_502_BAD_GATEWAY
            )
        all_employees = employees_response.json()
    except requests.exceptions.RequestException as e:
        return Response(
            {"error": f"Could not connect to employee service: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )

    # Filter employees by tenant_id (and optionally employee_id)
    target_employees = []
    for emp in all_employees:
        emp_tenant = emp.get('tenant_id')
        emp_employee = emp.get('employee_id')
        if emp_tenant is not None and str(emp_tenant) == tenant_id:
            if not employee_id or (emp_employee is not None and str(emp_employee) == employee_id):
                target_employees.append(emp)

    if not target_employees:
        return Response(
            {"error": "No matching employees found for the specified tenant_id (and employee_id)"},
            status=status.HTTP_404_NOT_FOUND
        )

    # 3. Fetch attendance records from employee_info service
    try:
        attendance_response = requests.get(f"{emp_api_url}/api/tenant/attendance/", timeout=5)
        all_attendance = attendance_response.json() if attendance_response.status_code == 200 else []
    except requests.exceptions.RequestException:
        all_attendance = []

    results = []
    
    for employee in target_employees:
        curr_emp_id = employee.get('employee_id')
        curr_emp_name = employee.get('employee_name')
        base_salary = employee.get('employee_salary', 0.0)

        # Count worked days (Present status in the target month/year)
        worked_days = 0
        for att in all_attendance:
            att_tenant = att.get('tenant_id')
            att_employee = att.get('employee_id')
            if (att_tenant is not None and str(att_tenant) == tenant_id and 
                att_employee is not None and str(att_employee) == str(curr_emp_id) and 
                att.get('status') == 'Present'):
                try:
                    att_date = datetime.strptime(att.get('attendance_date'), "%Y-%m-%d").date()
                    if att_date.year == year and att_date.month == month:
                        worked_days += 1
                except (ValueError, TypeError):
                    continue

        # 4. Fetch approved LOP leave requests
        lop_days = 0
        try:
            leaves_url = f"{emp_api_url}/api/leave/requests/?employee_id={curr_emp_id}&tenant_id={tenant_id}&status=Approved"
            leaves_response = requests.get(leaves_url, timeout=5)
            if leaves_response.status_code == 200:
                leaves = leaves_response.json()
                for leave in leaves:
                    if leave.get('leave_type') == 'LOP':
                        try:
                            start_date_val = datetime.strptime(leave.get('start_date'), "%Y-%m-%d").date()
                            end_date_val = datetime.strptime(leave.get('end_date'), "%Y-%m-%d").date()
                            
                            # Find overlap days with target month
                            overlap_start = max(start_date_val, month_start)
                            overlap_end = min(end_date_val, month_end)
                            
                            if overlap_start <= overlap_end:
                                overlap_days = (overlap_end - overlap_start).days + 1
                                lop_days += overlap_days
                        except (ValueError, TypeError):
                            continue
        except requests.exceptions.RequestException:
            # Fallback if leave service is unavailable: assume 0 LOP days
            lop_days = 0

        # 5. Salary calculation formula
        daily_rate = base_salary / total_days if total_days > 0 else 0.0
        deductions = round(lop_days * daily_rate, 2)
        net_salary = round(max(base_salary - deductions, 0.0), 2)

        existing_paid_salary = EmployeeSalary.objects.filter(
            tenant_id=tenant_id,
            employee_id=curr_emp_id,
            month=month,
            year=year,
            status='Paid',
        ).first()

        if existing_paid_salary:
            serializer = EmployeeSalarySerializer(existing_paid_salary)
            results.append(serializer.data)
            continue

        # 6. Save or update the record in the database
        salary_record, created = EmployeeSalary.objects.update_or_create(
            tenant_id=tenant_id,
            employee_id=curr_emp_id,
            month=month,
            year=year,
            defaults={
                'employee_name': curr_emp_name,
                'base_salary': base_salary,
                'worked_days': worked_days,
                'lop_days': lop_days,
                'total_days': total_days,
                'deductions': deductions,
                'net_salary': net_salary,
                'status': 'Calculated'
            }
        )
        
        serializer = EmployeeSalarySerializer(salary_record)
        results.append(serializer.data)

    return Response({
        "Message": f"Salary calculated successfully for {len(results)} employee(s)",
        "data": results if employee_id else results
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def salary_list(request):
    """
    List calculated salaries.
    Supports filtering by tenant_id, employee_id, month, year, status.
    """
    queryset = EmployeeSalary.objects.all()
    tenant_id = request.query_params.get('tenant_id')
    employee_id = request.query_params.get('employee_id')
    month = request.query_params.get('month')
    year = request.query_params.get('year')
    salary_status = request.query_params.get('status')

    if tenant_id:
        queryset = queryset.filter(tenant_id=tenant_id)
    if employee_id:
        queryset = queryset.filter(employee_id=employee_id)
    if month:
        queryset = queryset.filter(month=month)
    if year:
        queryset = queryset.filter(year=year)
    if salary_status:
        queryset = queryset.filter(status=salary_status)

    serializer = EmployeeSalarySerializer(queryset, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT'])
def pay_salary(request, pk):
    """
    Mark a calculated salary as Paid.
    """
    try:
        salary_record = EmployeeSalary.objects.get(id=pk)
    except EmployeeSalary.DoesNotExist:
        return Response({"error": "Salary record not found"}, status=status.HTTP_404_NOT_FOUND)

    salary_record.status = 'Paid'
    salary_record.save()
    serializer = EmployeeSalarySerializer(salary_record)
    return Response({
        "Message": "Salary marked as Paid successfully",
        "data": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT'])
def cancel_salary(request, pk):
    """
    Mark a calculated salary as Cancelled.
    """
    try:
        salary_record = EmployeeSalary.objects.get(id=pk)
    except EmployeeSalary.DoesNotExist:
        return Response({"error": "Salary record not found"}, status=status.HTTP_404_NOT_FOUND)

    if salary_record.status == 'Paid':
        return Response(
            {"error": "Paid salary records cannot be cancelled"},
            status=status.HTTP_400_BAD_REQUEST
        )

    salary_record.status = 'Cancelled'
    salary_record.save()
    serializer = EmployeeSalarySerializer(salary_record)
    return Response({
        "Message": "Salary cancelled successfully",
        "data": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
def delete_salary(request, pk):
    """
    Delete a calculated salary record.
    """
    try:
        salary_record = EmployeeSalary.objects.get(id=pk)
    except EmployeeSalary.DoesNotExist:
        return Response({"error": "Salary record not found"}, status=status.HTTP_404_NOT_FOUND)

    salary_record.delete()
    return Response({"Message": "Salary record deleted successfully"}, status=status.HTTP_200_OK)
