from django.contrib import admin

from .models import Machine, InventoryChange


class InventoryChangeInline(admin.TabularInline):
    model = InventoryChange
    extra = 0
    readonly_fields = ("field", "old_value", "new_value", "changed_at")
    can_delete = False
    ordering = ("-changed_at",)


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("pc", "cabinet", "is_teacher", "cpu", "ram", "motherboard", "ssd", "gpu", "last_update", "last_seen")
    list_filter = ("is_teacher", "cabinet")
    search_fields = ("pc", "cabinet", "cpu", "ram", "motherboard", "ssd", "gpu")
    inlines = [InventoryChangeInline]


@admin.register(InventoryChange)
class InventoryChangeAdmin(admin.ModelAdmin):
    list_display = ("machine", "field", "old_value", "new_value", "changed_at")
    list_filter = ("field",)
    search_fields = ("machine__pc",)
