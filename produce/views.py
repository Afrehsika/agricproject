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
            
        serializer = ProduceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(farmer=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
