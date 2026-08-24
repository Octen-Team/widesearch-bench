"""WideSearch-Bench: isolating the value of retrieval width at the API layer."""
from .schema import Task, TaskType, GoldEntity, ArmRun, load_tasks
from .grading import grade, Grade
from .stats import paired_compare, bootstrap_ci

__all__ = ["Task", "TaskType", "GoldEntity", "ArmRun", "load_tasks",
           "grade", "Grade", "paired_compare", "bootstrap_ci"]
__version__ = "0.1.0"
