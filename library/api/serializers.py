from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Author, Category, Book, Borrow
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from drf_yasg.utils import swagger_serializer_method

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'penalty_points']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ['id', 'name', 'bio']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class BookSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.all(), source='author', write_only=True
    )
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )

    class Meta:
        model = Book
        fields = ['id', 'title', 'description', 'total_copies', 'available_copies', 'author', 'author_id', 'category', 'category_id']

    def validate(self, data):
        """
        Ensure total_copies and available_copies are non-negative and consistent.
        """
        total_copies = data.get('total_copies', getattr(self.instance, 'total_copies', 0))
        available_copies = data.get('available_copies', getattr(self.instance, 'available_copies', 0))
        if total_copies < 0 or available_copies < 0:
            raise serializers.ValidationError("Total and available copies cannot be negative.")
        if available_copies > total_copies:
            raise serializers.ValidationError("Available copies cannot exceed total copies.")
        return data


class BorrowSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    book = serializers.StringRelatedField(read_only=True)
    book_id = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all(), source='book')

    class Meta:
        model = Borrow
        fields = ['id', 'user', 'book', 'book_id', 'borrow_date', 'due_date', 'return_date']
        extra_kwargs = {
            'due_date': {'required': False, 'read_only': True},
        }

    def validate(self, data):
        if 'request' not in self.context:
            raise serializers.ValidationError("Request context is required.")
        
        user = self.context['request'].user
        book = data['book']

        if not user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated.")
        
        if user.penalty_points >= 50:
            raise serializers.ValidationError("Too many penalty points to borrow.")
        
        active_borrows = Borrow.objects.filter(user=user, return_date__isnull=True).count()
        if active_borrows >= 3:
            raise serializers.ValidationError("User cannot borrow more than 3 books.")

        if book.available_copies <= 0:
            raise serializers.ValidationError("No available copies of this book.")

        return data

    def create(self, validated_data):
        with transaction.atomic():
            book = validated_data['book']
            user = self.context['request'].user
            book.available_copies -= 1
            book.save()
            borrow = Borrow.objects.create(
                user=user,
                book=book,
                borrow_date=timezone.now(),
                due_date=timezone.now() + timedelta(days=14),
            )
            return borrow

class ReturnSerializer(serializers.Serializer):
    borrow_id = serializers.IntegerField()

    def validate_borrow_id(self, value):
        # Ensure request context is available
        if 'request' not in self.context:
            raise serializers.ValidationError("Request context is required.")
        
        try:
            borrow = Borrow.objects.get(id=value, return_date__isnull=True)
            if borrow.user != self.context['request'].user:
                raise serializers.ValidationError("You can only return your own borrowed books.")
            return value
        except Borrow.DoesNotExist:
            raise serializers.ValidationError("Invalid or already returned borrow record.")

    def save(self):
        with transaction.atomic():
            borrow = Borrow.objects.get(id=self.validated_data['borrow_id'])
            book = borrow.book
            user = borrow.user
            borrow.return_date = timezone.now()
            book.available_copies += 1
            if borrow.return_date > borrow.due_date:
                days_late = max((borrow.return_date - borrow.due_date).days, 0)  # Ensure non-negative
                user.penalty_points += days_late * 2
            borrow.save()
            book.save()
            user.save()
            return borrow