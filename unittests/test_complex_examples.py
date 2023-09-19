from dataclasses import dataclass
from typing import Any, Generator, Optional

from frozendict import frozendict

from pvframework import ParallelQueryMappedValidator, Query, ValidationManager, Validator
from pvframework.utils import param


class TestComplexExamples:
    async def test_parallel_query_mapped_validator_multiple_argument(self):
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
                if not iban[:2].isalpha() or not iban[2:].isnumeric():
                    raise ValueError(f"{param('iban').param_id} is not a valid IBAN")

        validate_iban = Validator(check_iban)

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
            banking_data_per_contract=frozendict(
                {
                    "contract_1": BankingData(iban="DE52940594210000082271"),
                    "contract_2": BankingData(iban="DEA9370400440532013000"),
                    "contract_3": BankingData(iban="DE89370400440532013001"),
                }
            ),
            paying_through_sepa=frozendict({"1": True, "2": True, "3": False}),
        )
        result = await manager.validate(data)
        assert result.num_errors_total == 1
        assert "contract_2" in str(result.all_errors[0])
