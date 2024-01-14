"""
Contains some useful utility functions to be used in validator functions.
"""
from typing import TYPE_CHECKING, Any, Optional, TypeVar, overload

from typeguard import TypeCheckError, check_type

if TYPE_CHECKING:
    pass

AttrT = TypeVar("AttrT")


def optional_field(obj: Any, attribute_path: str, attribute_type: type[AttrT]) -> Optional[AttrT]:
    """
    Tries to query the `obj` with the provided `attribute_path`. If it is not existent, `None` will be returned.
    If the attribute is found, the type will be checked and TypeError will be raised if the type doesn't match the
    value.
    """
    try:
        return required_field(obj, attribute_path, attribute_type)
    except (AttributeError, TypeError):
        return None


@overload
def required_field(
    obj: Any, attribute_path: str, attribute_type: type[AttrT], param_base_path: Optional[str] = None
) -> AttrT:
    ...


@overload
def required_field(obj: Any, attribute_path: str, attribute_type: Any, param_base_path: Optional[str] = None) -> Any:
    ...


def required_field(obj: Any, attribute_path: str, attribute_type: Any, param_base_path: Optional[str] = None) -> Any:
    """
    Tries to query the `obj` with the provided `attribute_path`. If it is not existent,
    an AttributeError will be raised.
    If the attribute is found, the type will be checked and TypeError will be raised if the type doesn't match the
    value.
    """
    current_obj: Any = obj
    splitted_path = attribute_path.split(".")
    for index, attr_name in enumerate(splitted_path):
        try:
            current_obj = getattr(current_obj, attr_name)
        except AttributeError as error:
            current_path = ".".join(splitted_path[0 : index + 1])
            if param_base_path is not None:
                current_path = f"{param_base_path}.{current_path}"
            raise AttributeError(f"{current_path}: Not found") from error
    try:
        check_type(current_obj, attribute_type)
    except TypeCheckError as error:
        current_path = attribute_path
        if param_base_path is not None:
            current_path = f"{param_base_path}.{attribute_path}"
        raise TypeCheckError(f"{current_path}: {error}") from error
    return current_obj
