from django.db import models


class Machine(models.Model):
    pc = models.CharField(max_length=100, unique=True)
    cpu = models.CharField(max_length=200, blank=True)
    ram = models.CharField(max_length=50, blank=True)
    motherboard = models.CharField(max_length=200, blank=True)
    ssd = models.CharField(max_length=200, blank=True)
    gpu = models.CharField(max_length=200, blank=True)
    last_update = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(auto_now=True)

    SPEC_FIELDS = ["cpu", "ram", "motherboard", "ssd", "gpu"]

    def __str__(self):
        return self.pc


class InventoryChange(models.Model):
    machine = models.ForeignKey(Machine, related_name="changes", on_delete=models.CASCADE)
    field = models.CharField(max_length=50)
    old_value = models.CharField(max_length=200, blank=True)
    new_value = models.CharField(max_length=200, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.machine.pc}: {self.field} {self.old_value!r} -> {self.new_value!r}"
