"""Auditoría Normativa F-DC-124: Prohibición Absoluta de APIs Externas de IA o Deep Learning (Act. 3.5)."""
import ast

from app.core.config import ROOT

FORBIDDEN_AI_PACKAGES = {
    "openai",
    "anthropic",
    "google.generativeai",
    "vertexai",
    "langchain",
    "llama_index",
    "torch",
    "tensorflow",
    "keras",
    "xgboost",
    "lightgbm",
    "prophet",
    "sklearn",
    "scikit_learn",
}


def test_no_forbidden_ai_or_opaque_ml_imports_in_codebase():
    app_dir = ROOT / "app"
    violations: list[str] = []

    for py_file in app_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0].lower()
                    if top_pkg in FORBIDDEN_AI_PACKAGES or alias.name.lower() in FORBIDDEN_AI_PACKAGES:
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_pkg = node.module.split(".")[0].lower()
                if top_pkg in FORBIDDEN_AI_PACKAGES or node.module.lower() in FORBIDDEN_AI_PACKAGES:
                    violations.append(f"{py_file.name}: from {node.module} import ...")

    req_file = ROOT / "requirements.txt"
    if req_file.exists():
        req_text = req_file.read_text(encoding="utf-8").lower()
        for pkg in FORBIDDEN_AI_PACKAGES:
            if pkg in req_text:
                violations.append(f"requirements.txt contiene paquete prohibido: {pkg}")

    assert not violations, f"Violación a la restricción F-DC-124 Act. 3.5 detectada: {violations}"
