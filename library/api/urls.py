from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, BookListView, BookDetailView, BookCreateUpdateView, AuthorView, CategoryView, BorrowView, ReturnView, UserPenaltyView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('books/', BookListView.as_view(), name='book_list'),
    path('books/<int:pk>/', BookDetailView.as_view(), name='book_detail'),
    path('books/create/', BookCreateUpdateView.as_view(), name='book_create'),
    path('authors/', AuthorView.as_view(), name='author_list'),
    path('categories/', CategoryView.as_view(), name='category_list'),
    path('borrow/', BorrowView.as_view(), name='borrow'),
    path('return/', ReturnView.as_view(), name='return'),
    path('users/<str:pk>/penalties/', UserPenaltyView.as_view(), name='user_penalty'),
]