from rest_framework import serializers

from .models import HistoricalCost, Part, Quote


class HistoricalCostSerializer(serializers.ModelSerializer):
    supplier = serializers.CharField(source="supplier.name", default="", read_only=True)

    class Meta:
        model = HistoricalCost
        fields = ["id", "unit_cost", "currency", "program", "model_year", "supplier", "source", "is_sample"]


class QuoteSerializer(serializers.ModelSerializer):
    supplier = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = Quote
        fields = [
            "id", "supplier", "material", "tolerance", "certifications", "unit_price", "currency",
            "quantity", "lead_time_days", "program", "quoted_at", "source",
        ]


class PartSerializer(serializers.ModelSerializer):
    latest_cost = serializers.SerializerMethodField()
    quote_count = serializers.IntegerField(source="quotes.count", read_only=True)

    class Meta:
        model = Part
        fields = ["id", "part_number", "description", "material", "process", "latest_cost", "quote_count"]

    def get_latest_cost(self, part):
        cost = part.costs.first()  # ordered newest model year first
        return HistoricalCostSerializer(cost).data if cost else None


class PartDetailSerializer(PartSerializer):
    costs = HistoricalCostSerializer(many=True, read_only=True)
    quotes = QuoteSerializer(many=True, read_only=True)

    class Meta(PartSerializer.Meta):
        fields = PartSerializer.Meta.fields + ["costs", "quotes"]
