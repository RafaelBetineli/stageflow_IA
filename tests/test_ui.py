import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from stageflow.extraction import OllamaError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = PROJECT_ROOT / "src" / "stageflow" / "ui.py"
EXAMPLE = (PROJECT_ROOT / "data" / "mensagem_zap.example.txt").read_text(encoding="utf-8")


class UserInterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_host = os.environ.get("OLLAMA_HOST")
        self.previous_database = os.environ.get("STAGEFLOW_DATABASE")
        self.temporary = tempfile.TemporaryDirectory()
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
        os.environ["STAGEFLOW_DATABASE"] = str(Path(self.temporary.name) / "ui.db")

    def tearDown(self) -> None:
        if self.previous_host is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = self.previous_host
        if self.previous_database is None:
            os.environ.pop("STAGEFLOW_DATABASE", None)
        else:
            os.environ["STAGEFLOW_DATABASE"] = self.previous_database
        self.temporary.cleanup()

    def test_initial_screen_loads_without_ollama(self) -> None:
        app = AppTest.from_file(str(APP), default_timeout=20).run()

        self.assertEqual(0, len(app.exception))
        self.assertEqual(["Mensagem do aluno"], [element.label for element in app.text_area])
        self.assertIn("Identificar e organizar", [element.label for element in app.button])

    def test_structured_message_opens_review_without_ai(self) -> None:
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.text_area[0].input(EXAMPLE)
        app.button[0].click().run()

        self.assertEqual(0, len(app.exception))
        self.assertIn("Continuar para complementação", [element.label for element in app.button])
        self.assertGreaterEqual(len(app.text_input), 10)

    def test_opens_automatic_calendar_and_activity_planner(self) -> None:
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.text_area[0].input(EXAMPLE)
        app.button[0].click().run()
        next_button = next(
            button for button in app.button if button.label == "Continuar para complementação"
        )
        next_button.click().run()

        self.assertEqual(0, len(app.exception))
        subheaders = [element.value for element in app.subheader]
        self.assertIn("3. Calendário automático", subheaders)
        self.assertIn("4. Atividades e distribuição de horas", subheaders)
        self.assertTrue(app.date_input)
        self.assertIn(
            "Baixar calendário em CSV",
            [element.label for element in app.get("download_button")],
        )
        self.assertIn(
            "Lista tabulada para copiar",
            [element.label for element in app.expander],
        )

    def _open_activity_planner(self) -> AppTest:
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        if app.toggle and not app.toggle[0].disabled:
            app.toggle[0].set_value(False).run()
        app.text_area[0].input(EXAMPLE)
        app.button[0].click().run()
        next(button for button in app.button if button.label == "Continuar para complementação").click().run()
        return app

    def test_header_shows_progress_and_escapes_student_context(self) -> None:
        app = self._open_activity_planner()
        data = app.session_state["sf_data"].copy()
        data["NOME_ALUNO"] = "Aluno <teste> & revisão"
        app.session_state["sf_data"] = data
        app.run()

        self.assertEqual(0, len(app.exception))
        markup = "\n".join(element.value for element in app.markdown)
        self.assertIn("Aluno &lt;teste&gt; &amp; revisão", markup)
        self.assertIn("Farmácia · Módulo VI", markup)
        self.assertIn('aria-current="step"', markup)
        self.assertEqual(2, markup.count('class="sf-step complete"'))

    def test_activity_cards_show_current_hours_and_escape_titles(self) -> None:
        app = self._open_activity_planner()
        next(field for field in app.text_area if field.label.startswith("Atividades escolhidas")).input(
            "Conferência <medicamentos>\nControle de estoque\nOrientação ao paciente"
        ).run()

        self.assertEqual(0, len(app.exception))
        markup = "\n".join(element.value for element in app.markdown)
        self.assertIn("Conferência &lt;medicamentos&gt;", markup)
        self.assertEqual(1, markup.count('<div class="sf-hours"><strong>54h</strong>'))
        self.assertEqual(2, markup.count('<div class="sf-hours"><strong>53h</strong>'))
        self.assertIn("160 / 160h", markup)
        next(field for field in app.checkbox if field.label == "Ajustar as horas diretamente").check().run()
        next(field for field in app.number_input if field.label == "Horas — atividade 1").set_value(100).run()

        markup = "\n".join(element.value for element in app.markdown)
        self.assertIn('<div class="sf-hours"><strong>100h</strong>', markup)
        self.assertIn("Horas definidas", markup)
        self.assertIn('class="sf-total invalid"', markup)
        self.assertEqual((), app.session_state["sf_allocations"])

    def test_requires_at_least_three_manual_activities(self) -> None:
        app = self._open_activity_planner()
        next(field for field in app.text_area if field.label.startswith("Atividades escolhidas")).input(
            "Atividade um\nAtividade dois"
        ).run()

        self.assertEqual((), app.session_state["sf_allocations"])
        self.assertIn(
            "Informe pelo menos 3 atividades distintas.",
            [message.value for message in app.error],
        )

    def test_suggestions_require_click_and_confirmation_before_replacing_titles(self) -> None:
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9/preview-test"
        titles = ("Conferência de mercadorias", "Gestão de estoque", "Acompanhamento da dispensação")
        with patch("stageflow.extraction.OllamaClient.list_models", return_value=("qwen3:8b",)), patch(
            "stageflow.activity_suggestions.ActivitySuggestionService.suggest", return_value=titles,
        ) as suggest:
            app = self._open_activity_planner()
            suggest.assert_not_called()
            text_area = next(field for field in app.text_area if field.label.startswith("Atividades escolhidas"))
            text_area.input("Atividade manual").run()
            suggest.assert_not_called()

            next(button for button in app.button if button.label == "Sugerir atividades com IA local").click().run()
            self.assertEqual(0, len(app.exception))
            suggest.assert_called_once_with(
                course="Farmácia", area="Drogaria", module="Módulo VI", count=3, previous_titles=(),
            )
            self.assertEqual("Atividade manual", app.session_state["sf_activity_text"])
            self.assertFalse(app.session_state["sf_ollama_busy"])
            app.run()
            suggest.assert_called_once()

            next(button for button in app.button if button.label == "Usar estas sugestões").click().run()
            self.assertEqual(0, len(app.exception))
            self.assertEqual("\n".join(titles), app.session_state["sf_activity_text"])
            self.assertEqual(160, sum(item.hours for item in app.session_state["sf_allocations"]))
            self.assertFalse(app.session_state["sf_confirmed"])
            suggest.assert_called_once()

    def test_failed_suggestions_preserve_manual_data_and_allow_retry(self) -> None:
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9/failure-test"
        with patch("stageflow.extraction.OllamaClient.list_models", return_value=("qwen3:8b",)), patch(
            "stageflow.activity_suggestions.ActivitySuggestionService.suggest",
            side_effect=OllamaError("Resposta inválida de teste"),
        ) as suggest:
            app = self._open_activity_planner()
            next(field for field in app.text_area if field.label.startswith("Atividades escolhidas")).input(
                "Atividade manual\nAtividade auxiliar\nAtividade complementar"
            ).run()
            next(field for field in app.number_input if field.label == "Peso").set_value(9).run()
            next(field for field in app.checkbox if field.label == "Ajustar as horas diretamente").check().run()
            next(field for field in app.number_input if field.label == "Horas — atividade 1").set_value(100).run()
            before = app.session_state["sf_data"].copy()
            next(button for button in app.button if button.label == "Sugerir atividades com IA local").click().run()
            self.assertEqual(0, len(app.exception))
            self.assertEqual(
                "Atividade manual\nAtividade auxiliar\nAtividade complementar",
                app.session_state["sf_activity_text"],
            )
            self.assertEqual(before, app.session_state["sf_data"])
            self.assertEqual(9, app.session_state["sf_activity_weight_1"])
            self.assertEqual(100, app.session_state["sf_activity_hours_1"])
            self.assertTrue(app.session_state["sf_manual_activity_hours"])
            self.assertFalse(app.session_state["sf_ollama_busy"])
            self.assertIsNone(app.session_state["sf_activity_request"])
            button = next(button for button in app.button if button.label == "Sugerir atividades com IA local")
            self.assertFalse(button.disabled)
            self.assertIn("Resposta inválida de teste", [message.value for message in app.error])
            app.run()
            suggest.assert_called_once()

    def test_discard_or_context_change_does_not_call_ai_again(self) -> None:
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9/discard-test"
        with patch("stageflow.extraction.OllamaClient.list_models", return_value=("qwen3:8b",)), patch(
            "stageflow.activity_suggestions.ActivitySuggestionService.suggest", return_value=("A", "B", "C"),
        ) as suggest:
            app = self._open_activity_planner()
            next(button for button in app.button if button.label == "Sugerir atividades com IA local").click().run()
            next(field for field in app.number_input if field.label == "Quantidade de atividades para sugerir").set_value(4).run()
            self.assertEqual((), app.session_state["sf_activity_suggestions"])
            suggest.assert_called_once()
            suggest.return_value = ("A", "B", "C", "D")
            next(button for button in app.button if button.label == "Sugerir atividades com IA local").click().run()
            next(button for button in app.button if button.label == "Descartar sugestões").click().run()
            self.assertEqual(0, len(app.exception))
            self.assertEqual((), app.session_state["sf_activity_suggestions"])
            self.assertEqual("", app.session_state["sf_activity_text"])
            self.assertEqual(2, suggest.call_count)

    def test_offline_activity_suggestions_are_disabled_but_manual_input_works(self) -> None:
        app = self._open_activity_planner()
        button = next(button for button in app.button if button.label == "Sugerir atividades com IA local")
        self.assertTrue(button.disabled)
        next(field for field in app.text_area if field.label.startswith("Atividades escolhidas")).input(
            "Atividade manual\nAtividade auxiliar\nAtividade complementar"
        ).run()
        self.assertEqual(0, len(app.exception))
        self.assertEqual(3, len(app.session_state["sf_allocations"]))

    def test_calculated_role_updates_when_course_changes(self) -> None:
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.text_area[0].input(EXAMPLE)
        app.button[0].click().run()
        next_button = next(
            button for button in app.button if button.label == "Continuar para complementação"
        )
        next_button.click().run()

        for course, expected_role in (
            ("Biomedicina", "Biomédico responsável técnico"),
            ("Farmácia", "Farmacêutico responsável técnico"),
        ):
            with self.subTest(course=course):
                course_selector = next(
                    field for field in app.selectbox if field.label == "Curso"
                )
                course_selector.select(course).run()

                self.assertEqual(0, len(app.exception))
                self.assertEqual(
                    expected_role, app.session_state["sf_data"]["CARGO_REPRESENTANTE"]
                )
                role_field = next(
                    field for field in app.text_input
                    if field.label == "Cargo do responsável técnico (calculado)"
                )
                self.assertEqual(expected_role, role_field.value)
                self.assertTrue(role_field.disabled)
                self.assertFalse(
                    any("Cargo incompatível" in message.value for message in app.error)
                )

        self.assertEqual("CRF-SP 000000", app.session_state["sf_data"]["CONSELHO_RT"])

    def test_received_data_persists_and_company_can_be_saved(self) -> None:
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.text_area[0].input(EXAMPLE)
        app.button[0].click().run()
        next_button = next(
            button for button in app.button if button.label == "Continuar para complementação"
        )
        next_button.click().run()

        self.assertEqual(0, len(app.exception))
        cnpj = next(field for field in app.text_input if field.label == "CNPJ da empresa")
        semester = next(
            field for field in app.text_input
            if field.label == "Semestre informado pelo aluno"
        )
        calculated_module = next(
            field for field in app.text_input if field.label == "Módulo calculado"
        )
        company_name = next(
            field for field in app.text_input if field.label == "Razão social"
        )
        self.assertEqual("00.000.000/0000-00", cnpj.value)
        self.assertEqual("8º semestre", semester.value)
        self.assertEqual("Módulo VI", calculated_module.value)
        self.assertTrue(calculated_module.disabled)
        self.assertEqual("Empresa Exemplo Ltda.", company_name.value)

        save = next(
            button for button in app.button if button.label == "Salvar ou atualizar empresa"
        )
        save.click().run()

        self.assertEqual(0, len(app.exception))
        self.assertIn(
            "Empresa salva localmente para os próximos estágios.",
            [message.value for message in app.success],
        )
        self.assertEqual("Aluno Exemplo", app.session_state["sf_data"]["NOME_ALUNO"])
        self.assertEqual("00000000", app.session_state["sf_data"]["RA_ALUNO"])
        self.assertEqual("00.000.000/0000-00", app.session_state["sf_data"]["CNPJ"])
        error_messages = [message.value for message in app.error]
        self.assertNotIn("Campo obrigatório: Nome do aluno.", error_messages)
        self.assertNotIn("Campo obrigatório: RA.", error_messages)
        self.assertNotIn("Campo obrigatório: CNPJ.", error_messages)


if __name__ == "__main__":
    unittest.main()
