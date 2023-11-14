"""
Contains functionality to analyze the result of a validation process
"""
import itertools
from typing import TYPE_CHECKING, Generic, Optional

from .errors import ErrorHandler, ValidationError, _IDType
from .types import DataSetT

if TYPE_CHECKING:
    from .execution import ValidationManager


def _extract_error_id(validation_error: ValidationError) -> _IDType:
    return validation_error.error_id


# pylint: disable=too-many-instance-attributes
class ValidationResult(Generic[DataSetT]):
    """
    The function `ValidationManager.validate` will return an instance of this class. This class provides properties
    for further analysis of the ValidationErrors raised during the process. Note that the values are calculated only
    if you use them - this saves some CPU time if you are only interested in e.g. the succeeding data sets.
    """

    def __init__(
        self,
        validation_manager: "ValidationManager[DataSetT]",
        error_handlers: dict[DataSetT, ErrorHandler[DataSetT]],
    ):
        self._error_handlers = error_handlers
        self._validation_manager = validation_manager

        self._succeeded_data_sets: Optional[list[DataSetT]] = None
        self._data_set_errors: Optional[dict[DataSetT, list[ValidationError]]] = None
        self._errors: Optional[list[ValidationError]] = None
        self._num_errors_per_id: Optional[dict[_IDType, int]] = None

        self._data_set_warnings: Optional[dict[DataSetT, list[ValidationError]]] = None
        self._warnings: Optional[list[ValidationError]] = None
        self._num_warnings_per_id: Optional[dict[_IDType, int]] = None

    def _determine_succeeds(self):
        """Determines which data sets succeeded and groups the validation errors per failed data set"""
        self._succeeded_data_sets = []
        self._data_set_errors = {}
        self._data_set_warnings = {}
        for data_set, error_handler in self._error_handlers.items():
            if len(error_handler.warning_excs) > 0:
                self._data_set_warnings[data_set] = list(
                    itertools.chain.from_iterable(error_handler.warning_excs.values())
                )
            if len(error_handler.error_excs) > 0:
                self._data_set_errors[data_set] = list(itertools.chain.from_iterable(error_handler.error_excs.values()))
            else:
                self._succeeded_data_sets.append(data_set)

    @property
    def succeeded_data_sets(self) -> list[DataSetT]:
        """List of data sets which got validated without any errors"""
        if self._succeeded_data_sets is None:
            self._determine_succeeds()
            assert self._succeeded_data_sets is not None
        return self._succeeded_data_sets

    @property
    def data_set_errors(self) -> dict[DataSetT, list[ValidationError]]:
        """Maps data sets in which errors got raised to a list of ValidationErrors"""
        if self._data_set_errors is None:
            self._determine_succeeds()
            assert self._data_set_errors is not None
        return self._data_set_errors

    @property
    def data_set_warnings(self) -> dict[DataSetT, list[ValidationError]]:
        """Maps data sets in which warnings got raised to a list of ValidationErrors"""
        if self._data_set_warnings is None:
            self._determine_succeeds()
            assert self._data_set_warnings is not None
        return self._data_set_warnings

    @property
    def total(self) -> int:
        """Number of all validated data sets"""
        return len(self._error_handlers)

    @property
    def num_succeeds(self) -> int:
        """Number of positively validated data sets (equivalent to `len(self.succeeded_data_sets)`)"""
        return len(self.succeeded_data_sets)

    @property
    def num_fails(self) -> int:
        """Number of negatively validated data sets (equivalent to `len(self.data_set_errors)`)"""
        return len(self.data_set_errors)

    @property
    def num_warnings(self) -> int:
        """
        Number of positively validated data sets but which raised warnings (equivalent to `len(self.data_set_warnings)`)
        """
        return len(self.data_set_warnings)

    @property
    def all_errors(self) -> list[ValidationError]:
        """
        This is a complete list of all ValidationErrors from all validated data sets.
        It is sorted by their error ID to enable grouping by it using itertools.
        """
        if self._errors is None:
            if len(self.data_set_errors) > 0:
                self._errors = sorted(
                    itertools.chain.from_iterable(self.data_set_errors.values()),
                    key=_extract_error_id,
                )
            else:
                self._errors = []
        return self._errors

    @property
    def all_warnings(self) -> list[ValidationError]:
        """
        This is a complete list of all ValidationErrors (raised as warnings) from all validated data sets.
        It is sorted by their error ID to enable grouping by it using itertools.
        """
        if self._warnings is None:
            if len(self.data_set_warnings) > 0:
                self._warnings = sorted(
                    itertools.chain.from_iterable(self.data_set_warnings.values()),
                    key=_extract_error_id,
                )
            else:
                self._warnings = []
        return self._warnings

    @property
    def num_errors_total(self) -> int:
        """Number of errors from all data sets in total"""
        return len(self.all_errors)

    @property
    def num_warnings_total(self) -> int:
        """Number of warnings from all data sets in total"""
        return len(self.all_warnings)

    @property
    def num_errors_per_id(self) -> dict[_IDType, int]:
        """
        This is a dictionary which maps the error ID to the number of times it occurred
        (taking all data sets into account).
        """
        if self._num_errors_per_id is None:
            self._num_errors_per_id = {
                key: sum(1 for _ in values_iter)
                for key, values_iter in itertools.groupby(self.all_errors, key=_extract_error_id)
            }
        return self._num_errors_per_id

    @property
    def num_warnings_per_id(self) -> dict[_IDType, int]:
        """
        This is a dictionary which maps the error ID to the number of times it got raised as a warning
        (taking all data sets into account).
        """
        if self._num_warnings_per_id is None:
            self._num_warnings_per_id = {
                key: sum(1 for _ in values_iter)
                for key, values_iter in itertools.groupby(self.all_warnings, key=_extract_error_id)
            }
        return self._num_warnings_per_id
