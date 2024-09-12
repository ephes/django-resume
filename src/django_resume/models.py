from django.db import models


class Person(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    plugin_data = models.JSONField(default=dict)

    def __repr__(self):
        return f"<{self.name}>"

    def __str__(self):
        return self.name
