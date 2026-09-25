"""Interface de linha de comando para automações e uso sem navegador."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .documents import DEFAULT_OUTPUT
from .validation import InputValidationError
from .workflow import StageFlow


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "mensagem_zap.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Identifica dados e preenche os documentos de estágio."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--sem-ia", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.input.is_file():
            raise FileNotFoundError(f"Arquivo de entrada não encontrado: {args.input}")
        message = args.input.read_text(encoding="utf-8")
        workflow = StageFlow.ollama(args.model)
        analysis = workflow.analyze(message, use_ai=not args.sem_ia)
        if analysis.extraction.ai_error:
            print(f"Aviso: {analysis.extraction.ai_error}", file=sys.stderr)
        errors = tuple(issue for issue in analysis.issues if issue.severity == "erro")
        if errors:
            raise InputValidationError(errors)
        paths = workflow.generate(
            analysis.extraction.fields,
            args.output,
            overwrite=args.overwrite,
        )
    except Exception as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    print("Documentos gerados:")
    for path in paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
