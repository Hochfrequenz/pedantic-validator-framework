"""
Contains some useful utility functions to be used in validator functions.
"""
import inspect
from typing import Optional

from pvframework.execution import ValidationManager
from pvframework.validator import Parameter, Parameters


def param(param_name: str) -> Parameter:
    """
    This function can only be used inside validator functions and will only work if the function is executed by the
    validation framework. If you run the validator function "by yourself" or use this function elsewhere it will
    raise a RuntimeError.
    When using inside a validator function, this function returns the Parameter object of the provided parameter name.
    E.g.:
    ```
    def validate_email(e_mail: Optional[str] = None):
        param_e_mail = param("e_mail")
        assert param_e_mail.name == "e_mail"
        if param_e_mail.provided:
            my_e_mail_validation(e_mail)
    ```
    """
    call_stack = inspect.stack()
    # call_stack[0] -> this function
    # call_stack[...]
    # call_stack[i-1] -> must be the validator function
    # call_stack[i] -> should be either `_execute_sync_validator` or `_execute_async_validator`
    frame_info_candidate = None
    for frame_info in call_stack[2:]:
        if frame_info.function in ("_execute_sync_validator", "_execute_async_validator"):
            frame_info_candidate = frame_info
            break
    validation_manager: Optional[ValidationManager] = None
    if frame_info_candidate is not None:
        try:
            validation_manager = frame_info_candidate.frame.f_locals["self"]
            if not isinstance(validation_manager, ValidationManager):
                validation_manager = None
        except KeyError:
            pass

    if validation_manager is None:
        raise RuntimeError(
            "This function only works if it is called somewhere inside a validator function "
            "(must be in the function stack) which is executed by the validation framework"
        )

    provided_params: Optional[Parameters] = validation_manager.info.current_provided_params
    assert provided_params is not None, "This shouldn't happen"
    if param_name not in provided_params:
        raise RuntimeError(
            f"Parameter provider {validation_manager.info.current_mapped_validator} "
            f"did not provide parameter information for parameter '{param_name}'"
        )
    return provided_params[param_name]
