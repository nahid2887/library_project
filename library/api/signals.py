from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from .models import Borrow
from django.utils import timezone
from datetime import timedelta
import re

@receiver(post_save, sender=Borrow)
def send_due_date_notification(sender, instance, created, **kwargs):
    if created:
        # Validate email format
        if not instance.user.email:
            raise ValidationError("User email is missing.")
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', instance.user.email):
            raise ValidationError("User email is invalid.")
        
        subject = f'Borrow Confirmation: {instance.book.title}'
        message = (
            f"Dear {instance.user.username},\n\n"
            f"You have borrowed '{instance.book.title}'.\n"
            f"Due Date: {instance.due_date.strftime('%Y-%m-%d')}\n"
            f"Please return it by the due date to avoid penalties.\n"
        )
        send_mail(
            subject,
            message,
            'from@example.com',
            [instance.user.email],
            fail_silently=False,
        )