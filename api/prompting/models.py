from django.db import models

from django.contrib.auth.models import User

# # Create your models here.
# class PromptTemplate(models.Model):
#     name = models.CharField(max_length=255)
#     prompt = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     variables = models.JSONField(default={})
#     python_code = models.TextField(null=True, blank=True)
#     created_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     output_type = models.CharField(
#         max_length=255, choices=[("text", "Text"), ("json", "JSON")]
#     )
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return self.name

#     def extract_variables(self):
#         variables = {}
#         for line in self.prompt.split("\n"):
#             if "{{" in line and "}}" in line:
#                 variable = line.split("{{")[1].split("}}")[0].strip()
#                 description = line.split(":")[1].strip()
#                 variables[variable] = description
#         return variables


# class PromptTemplateVersion(models.Model):
#     prompt_template = models.ForeignKey(PromptTemplate, on_delete=models.CASCADE)
#     version = models.IntegerField(default=1)
#     prompt = models.TextField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     created_by = models.ForeignKey(User, on_delete=models.CASCADE)

#     def __str__(self):
#         return self.prompt_template.name
