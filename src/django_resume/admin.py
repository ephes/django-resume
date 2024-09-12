from django.contrib import admin

from .models import Person

admin.site.register(Person)
class PersonAdmin(admin.ModelAdmin):
    fields = ("name", "slug", "plugin_data")