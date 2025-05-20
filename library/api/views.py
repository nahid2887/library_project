from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny  # Import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg.utils import swagger_auto_schema
from .models import User, Author, Category, Book, Borrow
from .serializers import UserSerializer, AuthorSerializer, CategorySerializer, BookSerializer, BorrowSerializer, ReturnSerializer
from api.permissions import IsAdminOrReadOnly, IsSelfOrAdmin


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]  # Use AllowAny directly


class BookListView(generics.ListAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['author__name', 'category__name']
    search_fields = ['title', 'description']


class BookDetailView(generics.RetrieveAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer


class BookCreateUpdateView(generics.CreateAPIView, generics.UpdateAPIView):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAdminOrReadOnly]


class AuthorView(generics.ListCreateAPIView):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAdminOrReadOnly]


class CategoryView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class BorrowView(generics.ListCreateAPIView):
    queryset = Borrow.objects.all()
    serializer_class = BorrowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Borrow.objects.filter(user=self.request.user, return_date__isnull=True)


class ReturnView(generics.CreateAPIView):
    serializer_class = ReturnSerializer
    permission_classes = [IsAuthenticated]


class UserPenaltyView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSelfOrAdmin]

    def get_object(self):
        return self.request.user if self.kwargs['pk'] == 'me' else User.objects.get(pk=self.kwargs['pk'])