from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import os
import json
from .serializers import *
from .code import bloc_handler
from .code import symbols
from .code.file_handling import handle_uploaded_file


import logging
logger = logging.getLogger("mainLogger")


class MainView(TemplateView):
    template_name = 'main.html'


class Ping(APIView):
    def get(self, request):
        return Response({"result": 'BLOC Services are fully operational.'}, status=status.HTTP_200_OK)


class AnalyzeFiles(APIView):
    def post(self, request):
        try:
            tweet_files = request.FILES.getlist('tweet_files')
            # Use tempfiles to convert the uploaded file to ones that can be accessed intuitively
            converted_files = []
            for file in tweet_files:
                converted_file = handle_uploaded_file(file)
                converted_files.append(converted_file.name)

            results = bloc_handler.analyze_tweet_file(converted_files)

            for temp_file in converted_files:
                os.remove(temp_file)

            return Response({"result": results}, status=status.HTTP_200_OK)
        except Exception as error:
            return Response({"error": f"Something went wrong: {error}"}, status=status.HTTP_400_BAD_REQUEST)


class AnalyzeUsers(APIView):
    def get(self, request):
        serializer = AnalyzeUserSerializer(data=request.GET)
        if serializer.is_valid():
            try:
                response = bloc_handler.analyze_user(serializer.validated_data['username'])
                return Response({"result": response}, status=status.HTTP_200_OK)
            except Exception as error:
                return Response({"error": f"Something went wrong: {error}"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Invalid username data."}, status=status.HTTP_400_BAD_REQUEST)


class GetSymbols(APIView):
    def get(self, request):
        try:
            response = json.dumps(symbols.get_all_symbols())
            return Response({"result": response}, status=status.HTTP_200_OK)
        except Exception as error:
            return Response({"error": f"Something went wrong: {error}"}, status=status.HTTP_400_BAD_REQUEST)