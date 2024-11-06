from .registry import plugin_registry
from .about import AboutPlugin
from .base import SimplePlugin, ListPlugin
from .cover import CoverPlugin
from .education import EducationPlugin
from .identity import IdentityPlugin
from .permission_denied import PermissionDeniedPlugin
from .projects import ProjectsPlugin
from .skills import SkillsPlugin
from .theme import ThemePlugin
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
    "PermissionDeniedPlugin",
    "ProjectsPlugin",
    "SimplePlugin",
    "SkillsPlugin",
    "ThemePlugin",
    "TokenPlugin",
]
