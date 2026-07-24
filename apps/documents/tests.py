# apps/documents/tests.py
from django.test import TestCase
from apps.documents.tasks import add

class CelerySmokeTest(TestCase):
    def test_add_task_runs_eagerly(self):
        result = add.delay(2, 3)
        self.assertEqual(result.get(timeout=5), 5)