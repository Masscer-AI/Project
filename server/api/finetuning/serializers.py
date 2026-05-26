from rest_framework import serializers

from .context_rules import validate_context_rules_for_storage
from .models import Completion, CompletionAssignment, TrainingGenerator


class TrainingGeneratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingGenerator
        fields = "__all__"


class CompletionSerializer(serializers.ModelSerializer):
    agents = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )
    agent_ids = serializers.SerializerMethodField()

    class Meta:
        model = Completion
        fields = [
            "id",
            "prompt",
            "answer",
            "context_rules",
            "created_at",
            "updated_at",
            "approved",
            "approved_by",
            "training_generator",
            "agents",
            "agent_ids",
        ]
        read_only_fields = ["created_at", "updated_at", "approved_by", "agent_ids"]

    def get_agent_ids(self, obj):
        if hasattr(obj, "_prefetched_objects_cache") and "assignments" in obj._prefetched_objects_cache:
            return [a.agent_id for a in obj.assignments.all()]
        return list(
            obj.assignments.values_list("agent_id", flat=True)
        )

    def validate_context_rules(self, value):
        return validate_context_rules_for_storage(value)

    def create(self, validated_data):
        agent_ids = validated_data.pop("agents", None)
        completion = Completion.objects.create(**validated_data)
        if agent_ids is not None:
            self._sync_assignments(completion, agent_ids)
        return completion

    def update(self, instance, validated_data):
        agent_ids = validated_data.pop("agents", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if agent_ids is not None:
            self._sync_assignments(instance, agent_ids)
        return instance

    def _sync_assignments(self, completion, agent_ids):
        from api.ai_layers.models import Agent

        agent_ids = list({int(a) for a in agent_ids if a is not None})
        existing = set(
            completion.assignments.values_list("agent_id", flat=True)
        )
        target = set(agent_ids)

        if completion.approved:
            for aid in existing - target:
                agent = Agent.objects.filter(id=aid).first()
                if agent:
                    completion.remove_from_agent_memory(agent)

        for aid in existing - target:
            completion.assignments.filter(agent_id=aid).delete()
        for aid in target - existing:
            CompletionAssignment.objects.create(
                completion=completion,
                agent_id=aid,
            )

        if completion.approved:
            completion.save_in_memory()
