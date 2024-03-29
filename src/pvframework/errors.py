"""
Contains functionality to handle all the ValidationErrors and creating error IDs.
"""

import asyncio
import hashlib
import logging
import random
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator, Generic, Optional, TypeAlias

from bidict import bidict

from .types import DataSetT, MappedValidatorT, ValidatorT
from .validator import Parameters

if TYPE_CHECKING:
    from .execution import ValidationManager


class ValidationMode(StrEnum):
    """
    The validator mode defines how the validator will be executed.
    If the mode is set to `ValidationMode.ERROR`, the data set will be marked as failed if the validator raises an
    exception.
    If the mode is set to `ValidationMode.WARNING`, the data set will be marked as succeeded if the validator raises an
    exception but the exception will be logged as warning.
    """

    ERROR = "error"
    WARNING = "warning"


def format_parameter_infos(
    validator: ValidatorT,
    provided_params: Parameters,
    start_indent: str = "",
    indent_step_size: str = "\t",
):
    """
    Nicely formats the parameter information for prettier output.
    """
    output = start_indent + "{"
    for param_name, param in validator.signature.parameters.items():
        is_provided = param_name in provided_params and provided_params[param_name].provided
        is_required = (
            validator.signature.parameters[param_name].default == validator.signature.parameters[param_name].empty
        )
        param_value = provided_params[param_name].value if is_provided else param.default
        if isinstance(param_value, str):
            param_value = f"'{param_value}'"
        if param_value is None:
            param_value = "None"
        param_description = (
            f"value={param_value}, "
            f"id={provided_params[param_name].param_id if param_name in provided_params else 'unprovided'}, "
            f"{'required' if is_required else 'optional'}, "
            f"{'provided' if is_provided else 'unprovided'}"
        )

        output += f"\n{start_indent}{indent_step_size}{param_name}: {param_description}"
    return f"{output}\n{start_indent}" + "}"


_IdentifierType: TypeAlias = tuple[str, str, int]
_IDType: TypeAlias = int
_ERROR_ID_MAP: bidict[_IdentifierType, _IDType] = bidict()


def _get_identifier(exc: Exception) -> _IdentifierType:
    """
    Returns the module name and line number inside the function and its function name where the exception was
    originally raised.
    This tuple serves as identifier to create an error ID later on.
    """
    current_traceback = exc.__traceback__
    assert current_traceback is not None
    while current_traceback.tb_next is not None:
        current_traceback = current_traceback.tb_next
    raising_module_path = current_traceback.tb_frame.f_code.co_filename
    return (
        Path(raising_module_path).name,
        current_traceback.tb_frame.f_code.co_name,
        current_traceback.tb_lineno - current_traceback.tb_frame.f_code.co_firstlineno,
    )


def _generate_new_id(identifier: _IdentifierType, last_id: Optional[_IDType] = None) -> _IDType:
    """
    Generate a new random id with taking the identifier as seed. If last_id is provided it will be used as seed instead.
    """
    if last_id is None:
        module_name_hash = int(hashlib.blake2s((identifier[0] + identifier[1]).encode(), digest_size=4).hexdigest(), 16)
        random.seed(module_name_hash)
    # This range has no further meaning, but you have to define it.
    rand_range = (1_000_000, 9_998_999)
    # This guarantees that functions with up to 1000 lines of code remain stable in their first digits if an error
    # changes in its line number inside the function.
    error_id_range = (1_000_000, 9_999_999)
    return (random.randint(*rand_range) + identifier[2] - error_id_range[0]) % (
        error_id_range[1] - error_id_range[0] + 1
    ) + error_id_range[0]


def _get_error_id(identifier: _IdentifierType) -> _IDType:
    """
    Returns a unique ID for the provided identifier.
    """
    if identifier not in _ERROR_ID_MAP:
        new_error_id = None
        while True:
            new_error_id = _generate_new_id(identifier, last_id=new_error_id)
            # pylint: disable=unsupported-membership-test
            # No clue why pylint thinks this is unsupported. The BidictBase class has a __contains__ method.
            if new_error_id not in _ERROR_ID_MAP.inverse:
                break
        _ERROR_ID_MAP[identifier] = new_error_id
    return _ERROR_ID_MAP[identifier]


class ValidationError(RuntimeError):
    """
    A unified schema for error messages occurring during validation.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        message_detail: str,
        cause: Exception,
        data_set: DataSetT,
        mapped_validator: MappedValidatorT,
        validation_manager: "ValidationManager[DataSetT]",
        error_id: _IDType,
    ):
        provided_params = validation_manager.info.running_tasks[
            validation_manager.info.tasks[mapped_validator]
        ].current_provided_params
        data_set_str = str(data_set)
        if len(data_set_str) > 80:
            data_set_str = data_set_str[:77] + "..."
        message = (
            f"{error_id}, {type(cause).__name__}: {message_detail}\n"
            f"\tDataSet: {data_set_str}\n"
            f"\tError ID: {error_id}\n"
            f"\tError type: {type(cause).__name__}\n"
            f"\tValidator function: {mapped_validator.name}"
        )
        if provided_params is not None:
            formatted_param_infos = format_parameter_infos(
                mapped_validator.validator,
                provided_params,
                start_indent="\t\t",
            )
            message += f"\n\tParameter information: \n{formatted_param_infos}"
        else:
            message += "\n\tParameter information: No info"
        super().__init__(message)
        self.cause = cause
        self.data_set = data_set
        self.mapped_validator = mapped_validator
        self.validation_manager = validation_manager
        self.error_id = error_id
        self.message_detail = message_detail
        self.provided_params = provided_params


class ErrorHandler(Generic[DataSetT]):
    """
    This class provides functionality to easily log any occurring error.
    It can save one exception for each validator function.
    """

    def __init__(self, data_set: DataSetT, logger: logging.Logger):
        self.data_set = data_set
        self.error_excs: dict[MappedValidatorT, list[ValidationError]] = {}
        self.warning_excs: dict[MappedValidatorT, list[ValidationError]] = {}
        self._logger = logger

    # pylint: disable=too-many-arguments
    async def catch(
        self,
        msg: str,
        error: Exception,
        mapped_validator: MappedValidatorT,
        validation_manager: "ValidationManager[DataSetT]",
        custom_error_id: Optional[int] = None,
        mode: ValidationMode = ValidationMode.ERROR,
    ):
        """
        Logs a new validation error with the defined message. The `error` parameter will be set as `__cause__` of the
        validation error.
        """
        error_id = _get_error_id(_get_identifier(error)) if custom_error_id is None else custom_error_id
        error_nested = ValidationError(
            msg,
            error,
            self.data_set,
            mapped_validator,
            validation_manager,
            error_id,
        )

        if mode == ValidationMode.ERROR:
            log_function = self._logger.exception
            excs_dict = self.error_excs
        elif mode == ValidationMode.WARNING:
            log_function = self._logger.warning
            excs_dict = self.warning_excs
        else:
            raise ValueError(f"Unknown validation mode: {mode}")

        log_function(
            str(error_nested),
            exc_info=error_nested,
        )
        async with asyncio.Lock():
            if mapped_validator not in excs_dict:
                excs_dict[mapped_validator] = []
            excs_dict[mapped_validator].append(error_nested)

    @asynccontextmanager
    async def pokemon_catcher(
        self,
        mapped_validator: MappedValidatorT,
        validation_manager: "ValidationManager[DataSetT]",
        custom_error_id: Optional[int] = None,
        mode: ValidationMode = ValidationMode.ERROR,
    ) -> AsyncGenerator[None, None]:
        """
        This is an asynchronous context manager to easily implement a pokemon-catcher to catch any errors inside
        the body and envelops these inside ValidationErrors.
        """
        try:
            yield None
        except asyncio.TimeoutError as error:
            await self.catch(
                f"Timeout ("
                f"{validation_manager.validators[mapped_validator].timeout.total_seconds()}"  # type:ignore[union-attr]
                f"s) during execution",
                error,
                mapped_validator,
                validation_manager,
                custom_error_id,
                mode,
            )
        except Exception as error:  # pylint: disable=broad-exception-caught
            await self.catch(str(error), error, mapped_validator, validation_manager, custom_error_id, mode)
