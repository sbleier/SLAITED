from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField

# ----------------------------
# User, Student, Teacher, Class
# ----------------------------

class User(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]

    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    list_of_classes = models.ManyToManyField('Class', blank=True, related_name='users')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='student_profile')

    def __str__(self):
        return f"Student: {self.user.name}"


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='teacher_profile')

    def __str__(self):
        return f"Teacher: {self.user.name}"


class Class(models.Model):
    class_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='classes')
    list_of_students = models.ManyToManyField(Student, blank=True, related_name='classes')
    assignments = models.ManyToManyField('GeneratedAssignment', blank=True, related_name='classes')

    def __str__(self):
        return self.name

# ----------------------------
# Assignment Requirements / Generated Assignments
# ----------------------------

StudentProficiencies = (
    ("beginner", "Beginner"),
    ("intermediate", "Intermediate"),
    ("advanced", "Advanced")
)

class AssignmentRequirement(models.Model):
    requirement_id = models.AutoField(primary_key=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='requirements')
    topic = models.CharField(max_length=255)
    guiding_question = models.TextField()  # Central question for the assignment
    student_proficiency = models.CharField(max_length=20, choices=StudentProficiencies, default="beginner")
    skills_to_target = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    include_epistemology_intro = models.BooleanField(default=False)
    ai_first_demonstrates = models.BooleanField(default=False)
    upload_primary_sources = models.BooleanField(default=False)
    chatbot_finds_sources = models.BooleanField(default=False)
    include_custom_historical_info = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Requirement: {self.topic}"


class GeneratedAssignment(models.Model):
    """
    Sources should be stored as a list of dicts with structure:
    [
        {
            "title": "Source Title",
            "author": "Author Name",
            "year": "1945",
            "text": "Full source text..."
        },
        ...
    ]
    """
    assignment_id = models.AutoField(primary_key=True)
    requirement = models.ForeignKey(AssignmentRequirement, on_delete=models.CASCADE, related_name='generated_assignments')
    sources = JSONField(blank=True, default=list)  # List of source dicts
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Assignment {self.assignment_id} for {self.requirement.topic}"

# ----------------------------
# Student Interaction
# ----------------------------

class StudentInteractionSession(models.Model):
    """
    session_data should contain:
    {
        "current_phase": "intro" | "source_loop" | "complete",
        "source_index": 0,
        "skill_index": 0,
        "skill_evidence": {
            "0_0": ["response1", "response2"],
            "0_1": [...],
            ...
        }
    }
    """
    session_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='sessions')
    assignment = models.ForeignKey(GeneratedAssignment, on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    session_data = JSONField(blank=True, default=dict)

    def __str__(self):
        return f"Session {self.session_id} for {self.student}"


class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    session = models.ForeignKey(StudentInteractionSession, on_delete=models.CASCADE, related_name='messages')
    request = JSONField()  # {"message": "...", "phase": "..."}
    response = JSONField()  # {"message": "..."}
    created_at = models.DateTimeField(auto_now_add=True)  # Changed from 'timestamp'

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message {self.message_id} in Session {self.session.session_id}"

# ----------------------------
# Sources / Uploaded Info (Not currently used)
# ----------------------------

class PrimarySource(models.Model):
    source_id = models.AutoField(primary_key=True)
    requirement = models.ForeignKey(AssignmentRequirement, on_delete=models.CASCADE, related_name='primary_sources')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_primary_sources')
    file_url = models.URLField()
    file_type = models.CharField(max_length=50)
    extracted_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Primary Source {self.source_id}"


class UploadedInfo(models.Model):
    info_id = models.AutoField(primary_key=True)
    requirement = models.ForeignKey(AssignmentRequirement, on_delete=models.CASCADE, related_name='uploaded_info')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_info')
    file_url = models.URLField()
    file_type = models.CharField(max_length=50)
    extracted_text = models.TextField(blank=True)
    used_in_rag = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Uploaded Info {self.info_id}"