from django.db import models

class PDFFile(models.Model):
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ParserConfiguration(models.Model):
    interval_minutes = models.PositiveIntegerField(default=60, help_text="Interval in minutes for the parser to run")
    last_run = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Parser Config (every {self.interval_minutes} minutes)"
