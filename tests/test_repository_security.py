import re
import unittest
from pathlib import Path

from docx import Document

from stageflow.template_engine import DocumentGenerator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")


class RepositorySecurityTests(unittest.TestCase):
    def test_versioned_text_contains_only_reserved_example_emails(self) -> None:
        paths = [
            *PROJECT_ROOT.glob("*.txt"),
            PROJECT_ROOT / "data" / "mensagem_zap.example.txt",
            *(PROJECT_ROOT / "src").rglob("*.py"),
        ]
        matches = [
            (path, email)
            for path in paths
            for email in EMAIL_PATTERN.findall(path.read_text(encoding="utf-8"))
            if not email.lower().endswith("@example.invalid")
        ]
        self.assertEqual([], matches)

    def test_templates_do_not_embed_personal_email_or_cpf(self) -> None:
        issues = []
        for path in (PROJECT_ROOT / "templates").rglob("*.docx"):
            document = Document(path)
            text = "\n".join(
                paragraph.text
                for paragraph in DocumentGenerator._iter_paragraphs(document)
            )
            issues.extend((path, email) for email in EMAIL_PATTERN.findall(text))
            issues.extend(
                (path, cpf)
                for cpf in CPF_PATTERN.findall(text)
                if cpf != "000.000.000-00"
            )
        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
