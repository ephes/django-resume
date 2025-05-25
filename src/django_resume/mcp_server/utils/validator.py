"""Code validation utilities for django-resume plugins."""

import re
import ast
from dataclasses import dataclass

from .django_setup import ensure_django_setup


@dataclass
class ValidationResult:
    """Result of code validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    suggestions: list[str]


class PluginValidator:
    """Validates plugin code for security and correctness."""

    # Dangerous patterns to check for
    DANGEROUS_PATTERNS = [
        r"exec\s*\(",
        r"eval\s*\(",
        r"__import__\s*\(",
        r"open\s*\(",
        r"file\s*\(",
        r"input\s*\(",
        r"raw_input\s*\(",
        r"compile\s*\(",
        r"globals\s*\(",
        r"locals\s*\(",
        r"vars\s*\(",
        r"dir\s*\(",
        r"hasattr\s*\(",
        r"getattr\s*\(",
        r"setattr\s*\(",
        r"delattr\s*\(",
        r"import\s+os",
        r"import\s+sys",
        r"import\s+subprocess",
        r"from\s+os\s+import",
        r"from\s+sys\s+import",
        r"from\s+subprocess\s+import",
    ]

    # Required patterns for valid plugins
    REQUIRED_PATTERNS = [
        r"class\s+\w+Form\s*\(",
        r"class\s+\w+Plugin\s*\(",
        r"from\s+django\s+import\s+forms",
        r"from\s+\.base\s+import\s+SimplePlugin",
    ]

    def __init__(self):
        # Django setup will be called when needed
        pass

    def validate_plugin_code(self, code: str) -> ValidationResult:
        """Validate plugin Python code."""
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                errors.append(f"Dangerous pattern detected: {pattern}")

        # Check for required patterns
        for pattern in self.REQUIRED_PATTERNS:
            if not re.search(pattern, code, re.IGNORECASE):
                errors.append(f"Missing required pattern: {pattern}")

        # Parse and validate AST
        try:
            tree = ast.parse(code)
            ast_validation = self._validate_ast(tree)
            errors.extend(ast_validation.errors)
            warnings.extend(ast_validation.warnings)
            suggestions.extend(ast_validation.suggestions)
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")

        # Validate Django form fields
        form_validation = self._validate_django_forms(code)
        errors.extend(form_validation.errors)
        warnings.extend(form_validation.warnings)
        suggestions.extend(form_validation.suggestions)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def validate_template_code(self, template_code: str) -> ValidationResult:
        """Validate Django template code."""
        ensure_django_setup()
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        try:
            from django.template import Template, TemplateSyntaxError

            Template(template_code)
        except TemplateSyntaxError as e:
            errors.append(f"Template syntax error: {e}")
        except Exception as e:
            errors.append(f"Template error: {e}")

        # Check for required template elements
        if "contenteditable" not in template_code.lower():
            warnings.append(
                "Template may be missing contenteditable elements for inline editing"
            )

        if "edit_url" not in template_code:
            warnings.append("Template may be missing edit_url for edit functionality")

        if "show_edit_button" not in template_code:
            warnings.append("Template may be missing show_edit_button logic")

        # Check for security issues
        if re.search(r"\{\{\s*.*\|safe\s*\}\}", template_code):
            warnings.append("Found |safe filter - ensure content is properly sanitized")

        if re.search(r"<script", template_code, re.IGNORECASE):
            errors.append("Script tags are not allowed in templates")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _validate_ast(self, tree: ast.AST) -> ValidationResult:
        """Validate AST for security and structure."""
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Check for class definitions
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        form_classes = [cls for cls in classes if cls.name.endswith("Form")]
        plugin_classes = [cls for cls in classes if cls.name.endswith("Plugin")]

        if not form_classes:
            errors.append("No form class found (should end with 'Form')")

        if not plugin_classes:
            errors.append("No plugin class found (should end with 'Plugin')")

        # Check for dangerous function calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["exec", "eval", "compile"]:
                        errors.append(f"Dangerous function call: {node.func.id}")

        # Check for proper inheritance
        for cls in plugin_classes:
            if not any(
                base.id == "SimplePlugin"
                for base in cls.bases
                if isinstance(base, ast.Name)
            ):
                errors.append(
                    f"Plugin class {cls.name} should inherit from SimplePlugin"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _validate_django_forms(self, code: str) -> ValidationResult:
        """Validate Django form field definitions."""
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Check for JSON serializable field types
        non_json_fields = ["DecimalField", "FileField", "ImageField", "FilePathField"]

        for field_type in non_json_fields:
            if field_type in code:
                warnings.append(f"{field_type} may not be JSON serializable")

        # Check for proper form field definitions
        if not re.search(r"forms\.\w+Field", code):
            warnings.append("No Django form fields found")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )


# Global instance
validator = PluginValidator()
