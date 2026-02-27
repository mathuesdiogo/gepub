from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.utils.datastructures import MultiValueDict

from .forms import ConversionJobForm


class ConversionJobFormTests(SimpleTestCase):
    def test_merge_requires_two_pdfs(self):
        file1 = SimpleUploadedFile("a.pdf", b"%PDF-1.7", content_type="application/pdf")
        form = ConversionJobForm(
            data={"tipo": "PDF_MERGE"},
            files=MultiValueDict({"input_file": [file1]}),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("arquivos_adicionais", form.errors)

    def test_pages_mask_validation(self):
        file1 = SimpleUploadedFile("a.pdf", b"%PDF-1.7", content_type="application/pdf")
        form = ConversionJobForm(
            data={"tipo": "PDF_SPLIT", "pages": "abc"},
            files=MultiValueDict({"input_file": [file1]}),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("pages", form.errors)

    def test_merge_accepts_multiple_pdfs(self):
        file1 = SimpleUploadedFile("a.pdf", b"%PDF-1.7", content_type="application/pdf")
        file2 = SimpleUploadedFile("b.pdf", b"%PDF-1.7", content_type="application/pdf")
        file3 = SimpleUploadedFile("c.pdf", b"%PDF-1.7", content_type="application/pdf")
        form = ConversionJobForm(
            data={"tipo": "PDF_MERGE"},
            files=MultiValueDict(
                {
                    "input_file": [file1],
                    "arquivos_adicionais": [file2, file3],
                }
            ),
        )
        self.assertTrue(form.is_valid(), form.errors)
