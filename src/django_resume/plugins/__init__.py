from .registry import plugin_registry
from .about import AboutPlugin
from .base import SimplePlugin, ListPlugin
from .cover import CoverPlugin
from .education import EducationPlugin
from .identity import IdentityPlugin
from .projects import ProjectsPlugin
from .skills import SkillsPlugin
from .tokens import TokenPlugin
from .timelines import EmployedTimelinePlugin, FreelanceTimelinePlugin


__all__ = [
    "AboutPlugin",
    "CoverPlugin",
    "EducationPlugin",
    "EmployedTimelinePlugin",
    "FreelanceTimelinePlugin",
    "IdentityPlugin",
    "ListPlugin",
    "plugin_registry",
    "ProjectsPlugin",
    "SimplePlugin",
    "SkillsPlugin",
    "TokenPlugin",
]
