from rest_framework import serializers
from .models import AssignmentRequirement, GeneratedAssignment, StudentInteractionSession

class AssignmentRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentRequirement
        fields = '__all__'

class GeneratedAssignmentSerializer(serializers.ModelSerializer):
    requirement = AssignmentRequirementSerializer(read_only=True)

    class Meta:
        model = GeneratedAssignment
        fields = '__all__'

class StudentInteractionSessionSerializer(serializers.ModelSerializer):
    assignment = GeneratedAssignmentSerializer(read_only=True)

    class Meta:
        model = StudentInteractionSession
        fields = '__all__'