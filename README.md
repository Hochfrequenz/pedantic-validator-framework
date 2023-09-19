# Pedantic Validator Framework

![Unittests status badge](https://github.com/Hochfrequenz/pedantic-validator-framework/workflows/Unittests/badge.svg)
![Coverage status badge](https://github.com/Hochfrequenz/pedantic-validator-framework/workflows/Coverage/badge.svg)
![Linting status badge](https://github.com/Hochfrequenz/pedantic-validator-framework/workflows/Linting/badge.svg)
![Black status badge](https://github.com/Hochfrequenz/pedantic-validator-framework/workflows/Formatting/badge.svg)


This package enables you to easily create functions to apply validation logic to your data. It is designed
to work with arbitrary object structures. The validation function can be `async` if you need this feature.

Validation functions take arguments which are collected from a data structure instance on validation. The way how you
collect the arguments is fully customizable. But we give some features to retrieve these data more easily.

## Features
- Functions can be `async` or synchronous.
- Function arguments can be combined from anywhere of the data structure.
- Function arguments can be optional by defining a default value. If the argument is not found in the data structure,
  the default value is used instead of failing the validation test.
- Function arguments must be fully type hinted. The framework will do an implicit type check before calling the
  validation function by using `typeguard`.
- Querying the data structure for those arguments is fully customizable:
  - You can define the location of the data as path notation like: `field_a_of_data_structure.field_b_of_field_a`
  - You can define iterators to apply validation logic e.g. on every element inside a list.
  - You can define a completely customized function to retrieve the data.
- Errors raised in validation functions during the validation process are handled by an error handler.
- Basic analysis of the result of a validated data structure.

## Installation
The package is [available on PyPI](https://pypi.org/project/pvframework/):
```bash
pip install pvframework
```

## Getting started
To validate an arbitrary object structure (called data structure in the following), you have to create a
`ValidationManager` instance which is unique for the type of the data structure. This instance can
register any mapped validators you want to use for your data structure.

Note that the data structure have to be hashable at least at validation time. This is needed for proper error handling.

```python
import asyncio
from pvframework import ValidationManager, PathMappedValidator, Validator

class MySubStructure:
    def __init__(self, y: str):
        self.y = y

    def __hash__(self):
        return hash(self.y)

class MyDataStructure:
    def __init__(self, x: MySubStructure):
        self.x = x

    def __hash__(self):
        return hash(self.x)

manager = ValidationManager[MyDataStructure]()

def check_z_is_a_number(z: str):
    if not z.isnumeric():
        raise ValueError("y is not a number")

manager.register(PathMappedValidator(Validator(check_z_is_a_number), {"z": "x.y"}))

data = MyDataStructure(MySubStructure("123"))
result = asyncio.get_event_loop().run_until_complete(manager.validate(data))
assert result.num_fails == 0
```

First, the function `check_y_is_a_number` is a simple function which takes a string and raises an error if the value
is not numeric. The naming of the parameter is not important.
The framework ensures that the value is a string before calling the function. So you don't have to do any instance
checks in your validation functions. Similarly, if the framework can't find the value in the data structure, it will
also be treated as failed. The type checks are done via `typeguard`.

Second, we have to create a validator of this function by passing it to its constructor. It only does some basic
analysis like inspecting the signature, determining required and optional arguments, etc. You could create subclasses
of this and passing it to customized `MappedValidator`s if needed.

Third, we need to tell the framework how it should retrieve the values for the arguments from the data structure.
For this, the framework provides two predefined `MappedValidator`s: `PathMappedValidator` and `QueryMappedValidator`.
The `QueryMappedValidator` is very powerful but might be a bit overkill in most cases. The `PathMappedValidator` is
a simpler way to define the location of the data for each argument using a path notation.
Between every point the framework will invoke  the `__getattr__` method to query through the data structure.
If you have any more complicated than that you can use the `QueryMappedValidator` or even create your own
`MappedValidator` subclass.

Last, you have to register the `MappedValidator` to the `ValidationManager`. You can than invoke the `validate`
method with one or more data structure instances. The `validate` method returns a `ValidationResult` instance which
provides some basic analysis of the validation result if needed. Note that these analysis are only triggered on
demand but the object will cache any results.

Note: The validate method is `async` because the validation functions can be `async` as well. Currently, we don't need
a synchronous alternative for the method but will come eventually.

## A more complex example

This example will demonstrate you how you can use the `QueryMappedValidator` which has to iterate parallel over
two dictionaries inside the data structure.

```python
import asyncio
from pvframework import (
    ValidationManager,
    ParallelQueryMappedValidator,
    Validator,
    Query,
)
from pvframework.types import SyncValidatorFunction
from pvframework.utils import param
from dataclasses import dataclass
from schwifty import IBAN
from typing import Optional, TypeAlias, Any, Generator
from frozendict import frozendict

@dataclass(frozen=True)
class BankingData:
    iban: str

@dataclass(frozen=True)
class Customer:
    name: str
    age: int
    banking_data_per_contract: frozendict[str, BankingData]
    # This maps a contract ID onto its payment information
    paying_through_sepa: frozendict[str, bool]
    # This stores for each contract ID if the customer pays using a SEPA mandate

def check_iban(sepa_zahler: bool, iban: Optional[str] = None):
    """
    If `sepa_zahler` is True `iban` is required and checked on syntax.
    If `sepa_zahler` is False the test passes.
    """
    if sepa_zahler:
        if iban is None:
            raise ValueError(f"{param('iban').param_id} is required for sepa_zahler")
        IBAN(iban).validate()

ValidatorType: TypeAlias = Validator[Customer, SyncValidatorFunction]
validate_iban: ValidatorType = Validator(check_iban)

def iter_contract_id_dict(some_dict: dict[str, Any]) -> Generator[tuple[Any, str], None, None]:
    return ((value, f"[contract_id={key}]") for key, value in some_dict.items())

manager = ValidationManager[Customer]()
manager.register(
    ParallelQueryMappedValidator(
        validate_iban,
        {
            "iban": Query().path("banking_data_per_contract").iter(iter_contract_id_dict).path("iban"),
            "sepa_zahler": Query().path("paying_through_sepa").iter(iter_contract_id_dict),
        },
    )
)

data = Customer(
    name="John Doe",
    age=42,
    banking_data_per_contract=frozendict({
        "contract_1": BankingData(iban="DE52940594210000082271"),
        "contract_2": BankingData(iban="DE89370400440532013000"),
        "contract_3": BankingData(iban="DE89370400440532013001"),
    }),
    paying_through_sepa=frozendict({"1": True, "2": True, "3": False}),
)
result = asyncio.get_event_loop().run_until_complete(manager.validate(data))
assert result.num_errors_total == 1
assert "contract_2" in str(result.all_errors[0])
```

In this case we are using a specialized version of the `QueryMappedValidator`. When having to iterate through
lists, dicts or similar the `QueryMappedValidator` will apply the validation function on every element of the
cartesian product of the iterators. I.e. for every possible combination. But we want the iterators to map
parallel. This is what the `ParallelQueryMappedValidator` does. If the iterators have different lengths which are not
`1`, it will *raise* an error. I.e. the `validate` method would crash.

If you are wondering about the iterator function `iter_contract_id_dict` and why it returns a tuple of the value and
a string:
The string is used for error reporting. If the validation function fails for the set of parameters, the framework
will use those strings to define the location of the parameter inside the data structure.


## How to use this Repository on Your Machine

Follow the instructions in our [Python template repository](https://github.com/Hochfrequenz/python_template_repository#how-to-use-this-repository-on-your-machine).

## Contribute

You are very welcome to contribute to this repository by opening a pull request against the main branch.
