from rest_framework import serializers
from .models import Chatbot, Node, Connection, UploadedFile
import base64

class UploadedFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = UploadedFile
        fields = ['id', 'chatbot', 'user_session', 'file', 'original_name', 'uploaded_at', 'file_url']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url') and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class NodeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_content = serializers.SerializerMethodField()

    class Meta:
        model = Node
        fields = '__all__'

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url') and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url') and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_content(self, obj):
        """Return base64 data URL for image or file to display in frontend"""
        try:
            if obj.image:
                ext = obj.image.name.split('.')[-1]
                mime_type = f"image/{ext}"
                with obj.image.open('rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                return f"data:{mime_type};base64,{encoded}"
            elif obj.file:
                ext = obj.file.name.split('.')[-1]
                mime_type = "application/octet-stream"
                with obj.file.open('rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                return f"data:{mime_type};base64,{encoded}"
        except (FileNotFoundError, ValueError, OSError):
            # Handle cases where the file doesn't exist or can't be read
            return None
        return None


class ConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Connection
        fields = '__all__'


class ChatbotSerializer(serializers.ModelSerializer):
    nodes = NodeSerializer(many=True, read_only=True)
    connections = ConnectionSerializer(many=True, read_only=True)
    uploaded_files = UploadedFileSerializer(many=True, read_only=True)

    class Meta:
        model = Chatbot
        fields = ['id', 'name', 'nodes', 'connections', 'uploaded_files']