from django.core.management.base import BaseCommand
from chat.models import User, Student, Teacher

class Command(BaseCommand):
    help = 'Create test users: 1 teacher and 1 student'

    def handle(self, *args, **options):
        # Create a teacher
        teacher_user = User.objects.create(
            name="Mr. Katz",
            email="teacher@example.com",
            role="teacher",
            password_hash="fakehash123"
        )
        Teacher.objects.create(user=teacher_user)

        # Create a student
        student_user = User.objects.create(
            name="Sara Bleier",
            email="sara@example.com",
            role="student",
            password_hash="fakehash123"
        )
        Student.objects.create(user=student_user)

        self.stdout.write(self.style.SUCCESS('Test teacher and student created successfully!'))