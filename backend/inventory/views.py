from rest_framework.views import APIView
from rest_framework.response import Response

from tg_service.main import send_specs_to_channel

from .models import Machine, InventoryChange, parse_pc_name
from .serializers import InventorySerializer


class InventoryView(APIView):
    def post(self, request):
        s = InventorySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        machine, created = Machine.objects.get_or_create(pc=data["pc"])
        if created:
            machine.cabinet, machine.is_teacher = parse_pc_name(data["pc"])

        changes = {}
        if not created:
            for f in Machine.SPEC_FIELDS:
                old, new = getattr(machine, f), data[f]
                if old != new:
                    changes[f] = {"old": old, "new": new}
                    InventoryChange.objects.create(
                        machine=machine, field=f, old_value=old, new_value=new)

        for f in Machine.SPEC_FIELDS:
            setattr(machine, f, data[f])
        machine.last_update = data["last_update"]
        machine.save()

        # В телеграм-группу шлём только когда есть что сообщить (новый ПК или
        # реальное изменение характеристик) — обычный heartbeat без изменений
        # группу не спамит. Сбой отправки не должен ронять ответ агенту.
        if created or changes:
            send_specs_to_channel(machine, created, changes)

        return Response({"status": "ok", "changed": bool(changes), "changes": changes})
