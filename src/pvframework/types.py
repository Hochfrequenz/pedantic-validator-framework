"""
Contains the types used in the validation framework
"""
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Protocol, TypeAlias, TypeVar

if TYPE_CHECKING:
    from .validator import MappedValidator, Validator


class Hashable(Protocol):
    """
    A protocol that defines the __hash__ method.
    """

    def __hash__(self) -> int:
        ...


DataSetT = TypeVar("DataSetT", bound=Hashable)
AsyncValidatorFunction: TypeAlias = Callable[..., Coroutine[Any, Any, None]]
SyncValidatorFunction: TypeAlias = Callable[..., None]
ValidatorFunction: TypeAlias = AsyncValidatorFunction | SyncValidatorFunction
ValidatorFunctionT = TypeVar("ValidatorFunctionT", SyncValidatorFunction, AsyncValidatorFunction)
ValidatorT: TypeAlias = "Validator[DataSetT, ValidatorFunctionT]"  # pylint: disable=invalid-name
MappedValidatorT: TypeAlias = "MappedValidator[DataSetT, ValidatorFunctionT]"  # pylint: disable=invalid-name
MappedValidatorSyncAsync: TypeAlias = (
    "MappedValidator[DataSetT, AsyncValidatorFunction] | MappedValidator[DataSetT, SyncValidatorFunction]"
)
