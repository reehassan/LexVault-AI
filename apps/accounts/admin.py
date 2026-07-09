# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model

User = get_user_model()

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "firm", "is_staff", "is_superuser")
    list_filter = ("firm", "is_staff", "is_superuser")
    search_fields = ("username", "email")