from dataclasses import dataclass, field


@dataclass
class ExportReport:
    mapped_plugins: list[str] = field(default_factory=list)
    # plugin name -> reason it was omitted (e.g. "no json_resume adapter")
    omitted_plugins: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    valid: bool = True
    validation_errors: list[str] = field(default_factory=list)
