from django.db import models
from django.contrib.auth.models import User, AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    native_language = models.CharField(max_length=50, blank=True, null=True)
    learning_language = models.CharField(max_length=50, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def get_profile(self):
        """Return profile data in a dictionary format"""
        return {
            'id': self.id,
            'username': self.user.username,
            'email': self.user.email,
            'native_language': self.native_language,
            'learning_language': self.learning_language,
            'profile_image': self.profile_image.url if self.profile_image else None,
            'is_teacher': self.user.is_teacher,
            'is_student': self.user.is_student,
        }
    
    class Meta:
        app_label = 'account'


# Extend the User model with custom fields
User.add_to_class('is_teacher', models.BooleanField(default=False))
User.add_to_class('is_student', models.BooleanField(default=False))


def authenticate(email, password):
    """Custom authenticate function that uses email instead of username"""
    try:
        user = User.objects.get(email=email)
        if user.check_password(password):
            return user
    except User.DoesNotExist:
        pass
    return None


# Create Profile automatically when a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()