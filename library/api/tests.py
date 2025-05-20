from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth import get_user_model
from api.models import Author, Category, Book, Borrow
from django.utils import timezone
from datetime import timedelta
from django.core import mail
from django.db import transaction

User = get_user_model()

class LibraryManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='adminpass123'
        )
        self.user = User.objects.create_user(
            username='testuser', email='testuser@example.com', password='testpass123'
        )
        self.author = Author.objects.create(name='John Doe', bio='Author bio')
        self.category = Category.objects.create(name='Fiction')
        self.book = Book.objects.create(
            title='Test Book',
            description='A test book',
            total_copies=5,
            available_copies=5,
            author=self.author,
            category=self.category
        )

    # Core Functionality Tests
    def test_register_user(self):
        """Test user registration endpoint"""
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.count(), 3)  # admin, testuser, newuser
        self.assertEqual(response.data['username'], 'newuser')

    def test_login_user(self):
        """Test JWT login endpoint"""
        url = reverse('token_obtain_pair')
        data = {'username': 'testuser', 'password': 'testpass123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_book_list(self):
        """Test listing books with filters"""
        url = reverse('book_list')
        response = self.client.get(url, {'category__name': 'Fiction'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Test Book')

    def test_book_detail(self):
        """Test retrieving book details"""
        url = reverse('book_detail', kwargs={'pk': self.book.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Test Book')

    def test_create_book_admin(self):
        """Test creating a book as admin"""
        self.client.force_authenticate(user=self.admin)
        url = reverse('book_create')
        data = {
            'title': 'New Book',
            'description': 'A new book',
            'total_copies': 3,
            'available_copies': 3,
            'author_id': self.author.id,
            'category_id': self.category.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Book.objects.count(), 2)

    def test_create_book_non_admin(self):
        """Test non-admin cannot create a book"""
        self.client.force_authenticate(user=self.user)
        url = reverse('book_create')
        data = {
            'title': 'New Book',
            'description': 'A new book',
            'total_copies': 3,
            'available_copies': 3,
            'author_id': self.author.id,
            'category_id': self.category.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)

    def test_borrow_book(self):
        """Test borrowing a book"""
        self.client.force_authenticate(user=self.user)
        url = reverse('borrow')
        data = {'book_id': self.book.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 4)
        self.assertEqual(Borrow.objects.count(), 1)

    def test_return_book(self):
        """Test returning a book"""
        self.client.force_authenticate(user=self.user)
        borrow = Borrow.objects.create(
            user=self.user,
            book=self.book,
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=14)
        )
        self.book.available_copies -= 1
        self.book.save()
        url = reverse('return')
        data = {'borrow_id': borrow.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 5)
        borrow.refresh_from_db()
        self.assertIsNotNone(borrow.return_date)

    def test_user_penalty_view(self):
        """Test viewing user penalties"""
        self.client.force_authenticate(user=self.user)
        url = reverse('user_penalty', kwargs={'pk': 'me'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['penalty_points'], 0)

    # Corner Case Tests
    def test_borrow_more_than_three_books(self):
        """Test that user cannot borrow more than 3 books"""
        self.client.force_authenticate(user=self.user)
        url = reverse('borrow')
        for i in range(3):
            book = Book.objects.create(
                title=f'Book {i}',
                total_copies=1,
                available_copies=1,
                author=self.author,
                category=self.category
            )
            response = self.client.post(url, {'book_id': book.id}, format='json')
            self.assertEqual(response.status_code, 201)
        response = self.client.post(url, {'book_id': self.book.id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('cannot borrow more than 3 books', str(response.data))

    def test_borrow_unavailable_book(self):
        """Test borrowing a book with no available copies"""
        self.client.force_authenticate(user=self.user)
        self.book.available_copies = 0
        self.book.save()
        url = reverse('borrow')
        response = self.client.post(url, {'book_id': self.book.id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('No available copies', str(response.data))

    def test_return_late_book_penalty(self):
        """Test penalty calculation for late return"""
        self.client.force_authenticate(user=self.user)
        borrow = Borrow.objects.create(
            user=self.user,
            book=self.book,
            borrow_date=timezone.now() - timedelta(days=20),
            due_date=timezone.now() - timedelta(days=6)
        )
        self.book.available_copies = 0
        self.book.save()
        url = reverse('return')
        response = self.client.post(url, {'borrow_id': borrow.id}, format='json')
        self.assertEqual(response.status_code, 201)
        self.user.refresh_from_db()
        self.assertEqual(self.user.penalty_points, 12)

    def test_return_nonexistent_borrow(self):
        """Test returning a non-existent borrow record"""
        self.client.force_authenticate(user=self.user)
        url = reverse('return')
        response = self.client.post(url, {'borrow_id': 999}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid or already returned', str(response.data))

    def test_return_another_users_book(self):
        """Test attempting to return another user's book"""
        other_user = User.objects.create_user(
            username='otheruser', email='other@example.com', password='otherpass123'
        )
        borrow = Borrow.objects.create(
            user=other_user,
            book=self.book,
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=14)
        )
        self.client.force_authenticate(user=self.user)
        url = reverse('return')
        response = self.client.post(url, {'borrow_id': borrow.id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('your own borrowed books', str(response.data))

    def test_invalid_book_creation(self):
        """Test creating a book with invalid data (e.g., negative copies)"""
        self.client.force_authenticate(user=self.admin)
        url = reverse('book_create')
        data = {
            'title': 'Invalid Book',
            'description': 'Invalid',
            'total_copies': -1,
            'available_copies': -1,
            'author_id': self.author.id,
            'category_id': self.category.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)

    # Signal Tests
    def test_due_date_notification_on_borrow_create(self):
        """Test that an email is sent when a borrow is created"""
        self.client.force_authenticate(user=self.user)
        url = reverse('borrow')
        data = {'book_id': self.book.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, f'Borrow Confirmation: {self.book.title}')
        self.assertEqual(email.to, [self.user.email])
        self.assertEqual(email.from_email, 'from@example.com')
        self.assertIn(f"Dear {self.user.username}", email.body)
        self.assertIn(self.book.title, email.body)
        expected_due_date = (timezone.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        self.assertIn(expected_due_date, email.body)

    def test_no_email_on_borrow_update(self):
        """Test that no email is sent when a borrow is updated"""
        borrow = Borrow.objects.create(
            user=self.user,
            book=self.book,
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=14)
        )
        mail.outbox = []
        borrow.return_date = timezone.now()
        borrow.save()
        self.assertEqual(len(mail.outbox), 0)



    def test_email_with_malformed_due_date(self):
        """Test email sending with a malformed due_date"""
        borrow = Borrow.objects.create(
            user=self.user,
            book=self.book,
            borrow_date=timezone.now(),
            due_date=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(borrow.due_date.strftime('%Y-%m-%d'), email.body)

    # Additional Test Cases
    def test_concurrent_borrow_email_notifications(self):
        """Test email notifications for multiple borrow requests"""
        self.client.force_authenticate(user=self.user)
        url = reverse('borrow')
        book2 = Book.objects.create(
            title='Book 2',
            total_copies=2,
            available_copies=2,
            author=self.author,
            category=self.category
        )

        responses = [
            self.client.post(url, {'book_id': self.book.id}, format='json'),
            self.client.post(url, {'book_id': book2.id}, format='json')
        ]

        for response in responses:
            self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 2)
        titles = [self.book.title, book2.title]
        for email in mail.outbox:
            self.assertIn(email.subject, [f'Borrow Confirmation: {title}' for title in titles])
            self.assertEqual(email.to, [self.user.email])

    def test_borrow_with_invalid_book_id(self):
        """Test borrowing with a non-existent book ID"""
        self.client.force_authenticate(user=self.user)
        url = reverse('borrow')
        data = {'book_id': 999}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('does not exist', str(response.data))

    def test_multiple_returns_same_borrow(self):
        """Test attempting to return the same borrow multiple times"""
        self.client.force_authenticate(user=self.user)
        borrow = Borrow.objects.create(
            user=self.user,
            book=self.book,
            borrow_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=14)
        )
        self.book.available_copies -= 1
        self.book.save()
        url = reverse('return')
        data = {'borrow_id': borrow.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid or already returned', str(response.data))

    def test_borrow_with_high_penalty_points(self):
        """Test borrowing when user has high penalty points"""
        self.user.penalty_points = 50
        self.user.save()
        self.client.force_authenticate(user=self.user)
        url = reverse('borrow')
        data = {'book_id': self.book.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Too many penalty points', str(response.data))