"""
Contains a PathMappedValidator which gets the values from the data set in a very simple way. If you need a more
customizable MappedValidator you may be interested in the `QueryMappedValidator`.
"""
from typing import Any, Generator

from frozendict import frozendict

from pvframework.types import DataSetT, ValidatorFunctionT, ValidatorT
from pvframework.utils.query_object import required_field
from pvframework.validator import MappedValidator, Parameter, Parameters


class PathMappedValidator(MappedValidator[DataSetT, ValidatorFunctionT]):
    """
    This mapped validator class is for the "every day" usage. It simply queries the data set by the given attribute
    paths.
    """

    def __init__(self, validator: ValidatorT, param_map: dict[str, str] | frozendict[str, str]):
        super().__init__(validator)
        self.param_map: frozendict[str, str] = param_map if isinstance(param_map, frozendict) else frozendict(param_map)
        self._validate_param_maps()

    def _validate_param_maps(self):
        """
        Checks if the parameter maps match to the validator signature.
        """
        mapped_params = set(self.param_map.keys())
        if not mapped_params <= self.validator.param_names:
            raise ValueError(f"{self.validator.name} has no parameter(s) {mapped_params - self.validator.param_names}")
        if not self.validator.required_param_names <= mapped_params:
            raise ValueError(
                f"{self.validator.name} misses parameter(s) {self.validator.required_param_names - mapped_params}"
            )

    def __eq__(self, other):
        return (
            isinstance(other, PathMappedValidator)
            and self.validator == other.validator
            and self.param_map == other.param_map
        )

    def __ne__(self, other):
        return (
            not isinstance(other, PathMappedValidator)
            or self.validator != other.validator
            or self.param_map != other.param_map
        )

    def __hash__(self):
        return hash(self.param_map) + hash(self.validator)

    def __str__(self):
        return f"PathMappedValidator({self.validator.name}, {dict(self.param_map)})"

    def provide(self, data_set: DataSetT) -> Generator[Parameters[DataSetT] | Exception, None, None]:
        """
        Provides all parameter maps to the ValidationManager. If a parameter list could not be filled correctly
        an error will be yielded.
        """
        parameter_values: dict[str, Parameter] = {}
        skip = False
        for param_name, attr_path in self.param_map.items():
            try:
                value: Any = required_field(data_set, attr_path, Any)
                provided = True
            except AttributeError as error:
                if param_name in self.validator.required_param_names:
                    query_error = AttributeError(f"{attr_path}: value not provided")
                    query_error.__cause__ = error
                    yield query_error
                    skip = True
                    break
                value = self.validator.signature.parameters[param_name].default
                provided = False
            parameter_values[param_name] = Parameter(
                mapped_validator=self,
                name=param_name,
                param_id=attr_path,
                value=value,
                provided=provided,
            )
        if not skip:
            yield Parameters(self, **parameter_values)

    def provision_indicator(self) -> dict[str, str]:
        return {
            param_name: f".{self.param_map.get(param_name, 'Unmapped')}" for param_name in self.validator.param_names
        }
