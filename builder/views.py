import json
import uuid
import base64
import pytz
import os
from datetime import datetime

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings

from .models import Chatbot, Node, Connection, UploadedFile
from .serializers import *
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework.views import APIView
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers

class ChatbotViewSet(viewsets.ModelViewSet):
    serializer_class = ChatbotSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['run', 'upload_file']:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Chatbot.objects.filter(user=self.request.user)
        return Chatbot.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser], permission_classes=[AllowAny])
    def upload_file(self, request):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({"error": "No file uploaded"}, status=400)
        node_type = request.data.get('node_type', 'file_upload')
        path = None
        if node_type == 'image':
            node = Node(image=uploaded)
            node.save()
            path = node.image.url
            node.delete()
        else:
            node = Node(file=uploaded)
            node.save()
            path = node.file.url
            node.delete()
        return Response({"file_url": path})

    @action(detail=True, methods=["post"], permission_classes=[AllowAny], authentication_classes=[])
    def run(self, request, pk=None):
        print(f"User authenticated? {request.user.is_authenticated}")
        print(f"User: {request.user}")

        try:
            chatbot = Chatbot.objects.get(pk=pk)
        except Chatbot.DoesNotExist:
            return Response({"error": "Chatbot not found."}, status=404)

        # Get session ID from request or generate new one
        session_id = request.data.get("session_id") or str(uuid.uuid4())
        user_inputs = request.data.get("user_inputs", {})
        current_node_id = request.data.get("current_node_id")
        
        # Check if a file was uploaded
        uploaded_file = request.FILES.get('file')
        file_info = None
        
        if uploaded_file:
            # Store the file
            file_dir = os.path.join(settings.MEDIA_ROOT, 'uploaded_files')
            os.makedirs(file_dir, exist_ok=True)
            
            # Save file information
            uploaded_file_obj = UploadedFile.objects.create(
                chatbot=chatbot,
                user_session=session_id,
                file=uploaded_file,
                original_name=uploaded_file.name
            )
            
            # Add file info to user_inputs
            file_info = {
                'id': uploaded_file_obj.id,
                'name': uploaded_file_obj.original_name,
                'url': uploaded_file_obj.file.url
            }
            user_inputs['uploaded_file'] = file_info

        flow_key = uuid.uuid4().hex.upper()
        user_id = str(request.user.id) if request.user.is_authenticated else str(uuid.uuid4())
        ack = f"1__{uuid.uuid4()}"
        message_id = f"{chatbot.id}_{uuid.uuid4()}"
        source_node_name = "SEND_MSG_OPTNS"

        transcript = []
        visited = set()
        last_user_input = user_inputs.get("input")

        # Determine starting node
        if current_node_id:
            current = chatbot.nodes.filter(id=current_node_id).first()
        else:
            start = chatbot.nodes.filter(node_type=Node.NodeType.GREETING).first()
            if not start:
                incoming_ids = set(Connection.objects.filter(chatbot=chatbot).values_list("to_node_id", flat=True))
                start = chatbot.nodes.exclude(id__in=incoming_ids).first()
            current = start

        steps = 0
        max_steps = 50
        message_to_be_displayed = None
        sent_greetings = set()

        while current and steps < max_steps:
            steps += 1
            visited.add(current.id)

            if current.node_type in [Node.NodeType.GREETING, Node.NodeType.MESSAGE]:
                if current.id not in sent_greetings and current.content:
                    transcript.append({"from": "bot", "type": "text", "text": current.content})
                    message_to_be_displayed = current.content
                    sent_greetings.add(current.id)
                conn = current.outgoing.first()
                current = conn.to_node if conn else None

            elif current.node_type == Node.NodeType.IMAGE:
                file_content = None
                if current.image:
                    try:
                        ext = current.image.name.split('.')[-1]
                        mime_type = f"image/{ext}"
                        with current.image.open('rb') as f:
                            encoded = base64.b64encode(f.read()).decode('utf-8')
                        file_content = f"data:{mime_type};base64,{encoded}"
                    except:
                        pass
                transcript.append({
                    "from": "bot",
                    "type": "image",
                    "url": current.image.url if current.image else None,
                    "file_content": file_content
                })
                message_to_be_displayed = "[Image]"
                conn = current.outgoing.first()
                current = conn.to_node if conn else None

            elif current.node_type == Node.NodeType.FILE_UPLOAD:
                # Check if a file was uploaded in this request
                if uploaded_file:
                    # File was uploaded, so continue to the next node
                    transcript.append({
                        "from": "bot",
                        "type": "text",
                        "text": current.content or "Thank you for uploading the file."
                    })
                    message_to_be_displayed = "Thank you for uploading the file."
                    conn = current.outgoing.first()
                    current = conn.to_node if conn else None
                else:
                    # No file uploaded, request the file
                    file_content = None
                    if current.file:
                        try:
                            with current.file.open('rb') as f:
                                encoded = base64.b64encode(f.read()).decode('utf-8')
                            file_content = f"data:application/octet-stream;base64,{encoded}"
                        except:
                            pass
                    transcript.append({
                        "from": "bot",
                        "type": "file_request",
                        "text": current.content or "Please upload a file",
                        "url": current.file.url if current.file else None,
                        "file_content": file_content
                    })
                    message_to_be_displayed = "Please upload a file"
                    break

            elif current.node_type == Node.NodeType.USER_INPUT:
                if last_user_input:
                    transcript.append({"from": "user", "type": "text", "text": last_user_input})
                    connections = current.outgoing.all()
                    current = connections[0].to_node if connections else None
                else:
                    if current.content:
                        transcript.append({"from": "bot", "type": "text", "text": current.content})
                        message_to_be_displayed = current.content
                    break

            elif current.node_type == Node.NodeType.BRANCH:
                connections = current.outgoing.all()
                matching_conn = None

                if last_user_input:
                    user_input_clean = last_user_input.strip().lower()
                    for conn in connections:
                        if conn.condition_value:
                            condition_clean = conn.condition_value.strip().lower()
                            if (condition_clean in user_input_clean
                                    or user_input_clean in condition_clean
                                    or condition_clean == user_input_clean):
                                matching_conn = conn
                                break
                    if not matching_conn:
                        transcript.append({"from": "bot", "type": "text",
                                           "text": "I'm sorry, I don't understand that."})
                        message_to_be_displayed = "I'm sorry, I don't understand that."
                        break
                elif connections:
                    matching_conn = connections[0]

                current = matching_conn.to_node if matching_conn else None
                last_user_input = None

            elif current.node_type == Node.NodeType.END:
                if current.content:
                    transcript.append({"from": "bot", "type": "text", "text": current.content})
                    message_to_be_displayed = current.content
                current = None
                break
            else:
                current = None

            if current and current.id in visited:
                break

        running = not bool(transcript)
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = timezone.now().astimezone(ist)
        iso_str = now_ist.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
        tz_offset = now_ist.strftime('%z')
        timestamp_fixed = iso_str + tz_offset

        response_data = {
            "messageToBeDisplayed": message_to_be_displayed or None,
            "user_id": user_id,
            "ack": ack,
            "message_id": message_id,
            "message": {
                "action": "typing_on" if running else "message",
                "type": "typing_indicator" if running else "message",
                "transcript": transcript,
                "current_node_id": current.id if current else None,
            },
            "sender": "bot",
            "timestamp": timestamp_fixed,
            "session_id": session_id,
            "flow_key": flow_key,
            "source_node_name": source_node_name,
            "bot_ref": chatbot.id
        }
        
        # Add file info to response if a file was uploaded
        if file_info:
            response_data["uploaded_file"] = file_info

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def save_graph(self, request, pk=None):
        chatbot = self.get_object()
        raw_nodes = request.data.get("nodes", "[]")
        raw_edges = request.data.get("edges", "[]")
        
        try:
            nodes = json.loads(raw_nodes) if isinstance(raw_nodes, str) else raw_nodes
            edges = json.loads(raw_edges) if isinstance(raw_edges, str) else raw_edges
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON for nodes/edges"}, status=400)

        id_map = {}
        existing_nodes = {str(node.id): node for node in chatbot.nodes.all()}
        
        with transaction.atomic():
            # Update or create nodes
            for n in nodes:
                node_type = n.get("_ntype")
                node_id = n.get("id")
                data = n.get("data", {})
                
                # Check if this is an existing node
                existing_node = existing_nodes.get(node_id)
                
                if existing_node:
                    # Update existing node
                    existing_node.node_type = node_type
                    existing_node.label = data.get("label", "")
                    existing_node.content = data.get("content", "")
                    existing_node.x = float(n.get("position", {}).get("x", 0))
                    existing_node.y = float(n.get("position", {}).get("y", 0))
                    
                    # Handle file upload if provided
                    file_obj = request.FILES.get(node_id)
                    if file_obj:
                        if node_type == "image":
                            existing_node.image.save(file_obj.name, file_obj)
                        elif node_type == "file_upload":
                            existing_node.file.save(file_obj.name, file_obj)
                    
                    existing_node.save()
                    id_map[node_id] = existing_node.id
                else:
                    # Create new node
                    file_obj = request.FILES.get(node_id)
                    
                    dbn = Node.objects.create(
                        chatbot=chatbot,
                        node_type=node_type,
                        label=data.get("label", ""),
                        content=data.get("content", ""),
                        image=file_obj if node_type == "image" and file_obj else None,
                        file=file_obj if node_type == "file_upload" and file_obj else None,
                        x=float(n.get("position", {}).get("x", 0)),
                        y=float(n.get("position", {}).get("y", 0)),
                    )
                    id_map[node_id] = dbn.id
            
            # Delete nodes that are no longer in the graph
            current_node_ids = [n.get("id") for n in nodes]
            for node_id, node in existing_nodes.items():
                if node_id not in current_node_ids:
                    node.delete()
            
            # Delete all existing connections
            chatbot.connections.all().delete()
            
            # Create new connections
            for e in edges:
                from_node_id = id_map.get(e.get("source"))
                to_node_id = id_map.get(e.get("target"))
                if from_node_id and to_node_id:
                    Connection.objects.create(
                        chatbot=chatbot,
                        from_node_id=from_node_id,
                        to_node_id=to_node_id,
                        condition_key=e.get("condition_key"),
                        condition_value=e.get("condition_value"),
                    )
        
        return Response({"success": True})


class NodeViewSet(viewsets.ModelViewSet):
    queryset = Node.objects.all()
    serializer_class = NodeSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class ConnectionViewSet(viewsets.ModelViewSet):
    queryset = Connection.objects.all()
    serializer_class = ConnectionSerializer


class UploadedFileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UploadedFileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UploadedFile.objects.filter(chatbot__user=self.request.user)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
