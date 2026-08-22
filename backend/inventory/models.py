import re

from django.db import models

# Имена ПК в кабинетах: ученические — "<кабинет>-<место>" (напр. "12-1", "12-2"),
# учительские — "main-<кабинет>" (напр. "main-12").
_TEACHER_PC_RE = re.compile(r"^main-(\d+)$", re.IGNORECASE)
_STUDENT_PC_RE = re.compile(r"^(\d+)-\d+$")


def parse_pc_name(pc: str) -> tuple[str, bool]:
    """Извлекает (кабинет, is_teacher) из имени ПК по принятому соглашению
    об именовании. Если имя не соответствует ни одному шаблону — кабинет
    остаётся пустым, is_teacher = False (можно поправить вручную в админке)."""
    m = _TEACHER_PC_RE.match(pc)
    if m:
        return m.group(1), True

    m = _STUDENT_PC_RE.match(pc)
    if m:
        return m.group(1), False

    return "", False


class Machine(models.Model):
    pc = models.CharField(max_length=100, unique=True)
    cabinet = models.CharField(max_length=20, blank=True)
    is_teacher = models.BooleanField(default=False)
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
