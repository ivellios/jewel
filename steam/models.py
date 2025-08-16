from django.db import models

# Create your models here.


class SteamGame(models.Model):
    appid = models.CharField(max_length=50)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
