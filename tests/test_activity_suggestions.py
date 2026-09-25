import json
import unittest
from unittest.mock import Mock, patch

from stageflow.activity_suggestions import ActivitySuggestionService
from stageflow.extraction import OllamaClient, OllamaError


class ActivitySuggestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = Mock(spec=OllamaClient)
        self.service = ActivitySuggestionService(self.client)
        self.arguments = dict(course="Farmácia", area="Drogaria", module="Módulo I", count=3)

    def test_returns_titles_with_context_and_recent_history(self) -> None:
        self.client.chat.return_value = json.dumps({
            "activities": ["Conferência de mercadorias", "Gestão de estoque", "Acompanhamento da dispensação"]
        })
        titles = self.service.suggest(**self.arguments, previous_titles=("Recebimento de medicamentos",))

        self.assertEqual(3, len(titles))
        messages, schema = self.client.chat.call_args.args
        self.assertEqual(["system", "user"], [message["role"] for message in messages])
        self.assertIn("Recebimento de medicamentos", messages[1]["content"])
        self.assertIn("Atividades-base podem ser reutilizadas", messages[1]["content"])
        self.assertEqual(3, schema["properties"]["activities"]["minItems"])
        self.assertEqual(3, schema["properties"]["activities"]["maxItems"])
        self.assertNotIn("fields", schema["properties"])
        self.assertNotIn("horas", schema["properties"])

    def test_rejects_malformed_response_without_partial_results(self) -> None:
        for response in (
            "texto livre", "[]", '{}', '{"activities": "Conferência"}',
            '{"activities": ["Conferência"]}',
            '{"activities": ["A", "B", 3]}',
            '{"activities": ["A", "B", ""]}',
            '{"activities": ["A", "B", "C"], "hours": 10}',
            json.dumps({"activities": ["A", "B", "C\nRelato"]}),
            json.dumps({"activities": ["A", "B", "C" * 161]}),
            json.dumps({"activities": ["Conferência", "conferencia!", "Estoque"]}),
        ):
            with self.subTest(response=response):
                self.client.chat.return_value = response
                with self.assertRaises(OllamaError):
                    self.service.suggest(**self.arguments)

    def test_rejects_invalid_count_and_module_before_calling_ai(self) -> None:
        for count in (0, 4, True, 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.service.suggest(**{**self.arguments, "count": count})
        with self.assertRaises(ValueError):
            self.service.suggest(**{**self.arguments, "module": "Módulo inexistente"})
        self.client.chat.assert_not_called()

    def test_limits_history_size(self) -> None:
        self.client.chat.return_value = '{"activities": ["A", "B", "C"]}'
        self.service.suggest(**self.arguments, previous_titles=tuple(f"Histórico {i}" for i in range(100)))
        prompt = self.client.chat.call_args.args[0][1]["content"]
        self.assertIn("Histórico 29", prompt)
        self.assertNotIn("Histórico 30", prompt)

    def test_communication_failure_is_not_hidden(self) -> None:
        self.client.chat.side_effect = OllamaError("Ollama indisponível")
        with self.assertRaisesRegex(OllamaError, "Ollama indisponível"):
            self.service.suggest(**self.arguments)

    def test_extraction_and_suggestions_use_separate_requests(self) -> None:
        client = OllamaClient(model="qwen3:8b")
        with patch.object(OllamaClient, "_request", side_effect=[
            {"message": {"content": json.dumps({"fields": [
                {"key": "NOME_ALUNO", "value": "Pessoa Exemplo", "source": "Pessoa Exemplo"}
            ]})}},
            {"message": {"content": '{"activities": ["A", "B", "C"]}'}},
        ]) as request:
            evidence, _ = client.extract("Nome aluno: Pessoa Exemplo", ("NOME_ALUNO",))
            ActivitySuggestionService(client).suggest(**self.arguments)

        self.assertEqual("Pessoa Exemplo", evidence[0].value)
        self.assertEqual(2, request.call_count)
        extraction = request.call_args_list[0].args[1]
        activities = request.call_args_list[1].args[1]
        self.assertIn("fields", extraction["format"]["properties"])
        self.assertIn("activities", activities["format"]["properties"])
        self.assertNotIn("Pessoa Exemplo", json.dumps(activities, ensure_ascii=False))
        self.assertEqual(2, len(activities["messages"]))
        self.assertFalse(activities["stream"])
        self.assertFalse(activities["think"])


if __name__ == "__main__":
    unittest.main()
