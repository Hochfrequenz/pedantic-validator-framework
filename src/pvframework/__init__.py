"""
This package enables you to easily create functions to apply validation logic to your data. It is designed
to work with arbitrary object structures.
"""

from .analysis import ValidationResult
from .execution import ValidationManager
from .mapped_validators import ParallelQueryMappedValidator, PathMappedValidator, Query, QueryMappedValidator
from .validator import MappedValidator, Validator
