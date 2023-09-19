"""
This module contains the ParallelQueryMappedValidator class.
"""
from typing import Any, Iterator, Optional

from pvframework.types import DataSetT, ValidatorFunctionT

from .query_map import QueryIterable, QueryMappedValidator


class ParallelQueryMappedValidator(QueryMappedValidator[DataSetT, ValidatorFunctionT]):
    """
    This mapped validator class supplies the parameter combinations not as cartesian product but as parallel.
    I.e. each iterator must yield the same number of values or have to be scalar.
    => For every parameter pair p_i, p_j: len(p_i) == len(p_j) or len(p_i) == 1 or len(p_j) == 1
    """

    def param_sets(self, param_iterables: dict[str, QueryIterable]) -> Iterator[dict[str, Any] | Exception]:
        """
        This method is a generator which yields a dict of parameter sets. Each parameter set is a dict of parameter
        names and values. The parameter sets are yielded in parallel. It behaves similar to zip.
        """
        for param_iterable in param_iterables.values():
            param_iterable.include_exceptions = True
        param_sets = {param_name: list(param_iterable) for param_name, param_iterable in param_iterables.items()}
        lengths = [len(param_set) for param_set in param_sets.values()]
        iter_count = 1
        for length in lengths:
            if 1 < iter_count != length:
                raise ValueError("All parameter sets must have the same length or be scalar")
            if length != iter_count:
                iter_count = length
        for i in range(iter_count):
            param_set: Optional[dict[str, Any]] = {
                param_name: param_values[0] if len(param_values) == 1 else param_values[i]
                for param_name, param_values in param_sets.items()
            }
            assert param_set is not None
            for param_name, param_value in param_set.items():
                if param_name in self.validator.required_param_names and isinstance(param_value, Exception):
                    yield param_value
                    param_set = None
                    break
            if param_set is not None:
                yield param_set
