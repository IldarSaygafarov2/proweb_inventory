from rest_framework import serializers


class InventorySerializer(serializers.Serializer):
    pc = serializers.CharField()
    cpu = serializers.CharField()
    ram = serializers.CharField()
    motherboard = serializers.CharField()
    ssd = serializers.CharField()
    gpu = serializers.CharField()
    last_update = serializers.DateTimeField(input_formats=["%Y-%m-%d %H:%M"])
