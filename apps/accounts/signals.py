from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if not created:
        return

    # cria profile com segurança
    try:
        with transaction.atomic():
            Profile.objects.get_or_create(user=instance)
    except IntegrityError:
        # se houver corrida/duplicidade, tenta pegar o existente
        Profile.objects.get_or_create(user=instance)
