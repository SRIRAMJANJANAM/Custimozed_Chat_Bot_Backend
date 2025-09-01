from django.db import models
from django.contrib.auth.models import User

class Chatbot(models.Model):
    name = models.CharField(max_length=120)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chatbots")

    def __str__(self):
        return self.name


class Node(models.Model):
    class NodeType(models.TextChoices):
        GREETING = "greeting", "Greeting"
        USER_INPUT = "user_input", "User Input"
        MESSAGE = "message", "Message"
        IMAGE = "image", "Image"
        FILE_UPLOAD = "file_upload", "File Upload"
        BRANCH = "branch", "Branch"
        END = "end", "End"

    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name="nodes")
    node_type = models.CharField(max_length=32, choices=NodeType.choices)
    label = models.CharField(max_length=120, blank=True)
    content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="chatbot_images/", blank=True, null=True)
    file = models.FileField(upload_to="chatbot_files/", blank=True, null=True)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)

    def __str__(self):
        return f"{self.chatbot.name}:{self.node_type}:{self.label or self.id}"


class Connection(models.Model):
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name="connections")
    from_node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="outgoing")
    to_node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="incoming")
    condition_value = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        unique_together = ("from_node", "to_node")

    def __str__(self):
        return f"{self.from_node_id} -> {self.to_node_id} ({self.condition_value})"


class UploadedFile(models.Model):
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='uploaded_files')
    user_session = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to='uploaded_files/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.original_name} ({self.user_session})"