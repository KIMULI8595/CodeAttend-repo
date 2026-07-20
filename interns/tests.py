from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase

from interns.admin import InternProfileAdmin
from interns.models import InternProfile


class InternProfileAdminTests(SimpleTestCase):
    def test_get_urls_registers_rejection_view(self):
        admin_site = AdminSite()
        model_admin = InternProfileAdmin(InternProfile, admin_site)

        urls = model_admin.get_urls()

        self.assertTrue(any(url.name == "reject-intern" for url in urls))
