from publicmapping.redistricting.models import *
from django.contrib import admin

class   CharacteristicInline(admin.TabularInline):
    model = Characteristic
   

class GeounitAdmin(admin.ModelAdmin):
    inlines = [CharacteristicInline]

admin.site.register(Geounit, GeounitAdmin)
admin.site.register(Characteristic)
admin.site.register(Subject)
admin.site.register(Geolevel)
admin.site.register(Plan)
admin.site.register(Target)
