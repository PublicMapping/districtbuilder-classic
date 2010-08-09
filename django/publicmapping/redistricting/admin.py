from publicmapping.redistricting.models import *
from django.contrib.gis import admin

class CharacteristicAdmin(admin.ModelAdmin):
    list_display = ('subject','geounit','number',)
    raw_id_fields = ('geounit',)

class CharacteristicInline(admin.TabularInline):
    model = Characteristic

class GeounitAdmin(admin.OSMGeoAdmin):
    inlines = [CharacteristicInline]
    list_display = ('name','geolevel',)
    ordering = ('name',)

class DistrictInline(admin.TabularInline):
    fields = ('district_id','name','version',)
    model = District

class DistrictAdmin(admin.OSMGeoAdmin):
    fields = ('district_id','name','plan','version','geom',)
    list_display = ('name','plan','version',)
    list_filter = ('plan',)
    ordering = ('name',)

class PlanAdmin(admin.ModelAdmin):
    inlines = [DistrictInline]
    list_display = ('name','is_template','is_temporary','owner','created','edited',)
    list_filter = ('is_template','is_temporary',)
    ordering = ('name',)

class SubjectAdmin(admin.ModelAdmin):
    list_display = ('display', 'short_display', 'is_displayed',)
    list_filter = ('is_displayed',)

admin.site.register(Geounit, GeounitAdmin)
admin.site.register(ComputedCharacteristic) 
admin.site.register(Characteristic, CharacteristicAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Geolevel)
admin.site.register(Plan, PlanAdmin)
admin.site.register(District, DistrictAdmin)
admin.site.register(Target)
