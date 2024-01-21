from django.db import models


class YourModel(models.Model):
    image = models.ImageField(upload_to='images')

    def __str__(self):
        return f'{self.area} - {self.id}'

    class Meta:
        app_label = 'app'
