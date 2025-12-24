from django.contrib import admin
from .models import User, Student, Teacher, Class, AssignmentRequirement, GeneratedAssignment, Message, StudentInteractionSession, PrimarySource, UploadedInfo

admin.site.register(User)
admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Class)
admin.site.register(AssignmentRequirement)
admin.site.register(GeneratedAssignment)
admin.site.register(Message)
admin.site.register(StudentInteractionSession)
admin.site.register(PrimarySource)
admin.site.register(UploadedInfo)