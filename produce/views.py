from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Produce
from .serializers import ProduceSerializer


class ProduceListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        produces = Produce.objects.filter(status='AVAILABLE')
        
        farmer_id = request.query_params.get('farmer')
        if farmer_id:
            produces = Produce.objects.filter(farmer_id=farmer_id)
            
        crop_name = request.query_params.get('crop')
        if crop_name:
            produces = produces.filter(name__icontains=crop_name)
            
        sort_by = request.query_params.get('sort')
        if sort_by == 'urgency':
            produces = sorted(produces, key=lambda p: p.freshness_score)
            serializer = ProduceSerializer(produces, many=True)
            return Response(serializer.data)
            
        produces = produces.order_by('-id')
        serializer = ProduceSerializer(produces, many=True)
        return Response(serializer.data)


class ProduceCreateView(APIView):
    def post(self, request):
        if request.user.role != 'FARMER':
            return Response({'detail': 'Only farmers can create listings'}, status=status.HTTP_403_FORBIDDEN)
            
        # Handle file upload for crop harvest picture
        image_file = request.FILES.get('image') or request.data.get('image')
        image_url = ""
        
        # Verify if it's a file upload
        if image_file and hasattr(image_file, 'name'):
            import os
            import uuid
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            
            # Generate unique filename to avoid conflict
            ext = os.path.splitext(image_file.name)[1]
            filename = f"{uuid.uuid4()}{ext}"
            
            # Save files in the static folder under uploads/
            upload_dir = os.path.join('static', 'uploads')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
                
            path = default_storage.save(os.path.join(upload_dir, filename), ContentFile(image_file.read()))
            image_url = f"/static/uploads/{filename}"
            
        data = request.data.copy()
        if image_url:
            data['image_url'] = image_url
            
        serializer = ProduceSerializer(data=data)
        if serializer.is_valid():
            serializer.save(farmer=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
