"""Kenya first-class market layer tests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from api.db.models import OrganizationModel
from api.services.crm.service import get_customer_service
from api.services.kenya.config import KENYA, KenyaLanguage
from api.services.kenya.context import attach_kenya_context, build_kenya_context
from api.services.kenya.currency import confirm_kes, parse_kes
from api.services.kenya.entities import extract_kenyan_entities
from api.services.kenya.formatters import format_kenya_datetime, format_kes
from api.services.kenya.holidays import is_kenya_public_holiday
from api.services.kenya.hours import is_within_business_hours
from api.services.kenya.language import identify_kenya_language
from api.services.kenya.phone import normalize_kenyan_phone
from api.services.kenya.pipeline import process_kenya_turn
from api.services.kenyan_intent.types import BusinessIntent


class TestKenyanPhoneNormalization:
    @pytest.mark.parametrize(
        "raw,e164,operator",
        [
            ("0712345678", "+254712345678", "safaricom"),
            ("0112345678", "+254112345678", "safaricom"),
            ("254712345678", "+254712345678", "safaricom"),
            ("254112345678", "+254112345678", "safaricom"),
            ("+254712345678", "+254712345678", "safaricom"),
            ("+254112345678", "+254112345678", "safaricom"),
            ("+254 712 345 678", "+254712345678", "safaricom"),
            ("0731234567", "+254731234567", "airtel"),
            ("0771234567", "+254771234567", "telkom"),
            ("0761234567", "+254761234567", "equitel"),
        ],
    )
    def test_valid_formats(self, raw, e164, operator):
        result = normalize_kenyan_phone(raw)
        assert result.valid
        assert result.e164 == e164
        assert result.original == raw
        assert result.operator == operator

    @pytest.mark.parametrize(
        "raw",
        ["", "abc", "123", "07212345", "+255712345678", "0201234567", "+254212345678"],
    )
    def test_invalid_numbers(self, raw):
        result = normalize_kenyan_phone(raw)
        assert not result.valid
        assert result.e164 is None
        assert result.original == raw


class TestKesCurrency:
    @pytest.mark.parametrize(
        "text,amount",
        [
            ("500 bob", Decimal("500.00")),
            ("five hundred", Decimal("500.00")),
            ("500 shillings", Decimal("500.00")),
            ("1,500", Decimal("1500.00")),
            ("one thousand five hundred", Decimal("1500.00")),
            ("2k", Decimal("2000.00")),
            ("2.5k", Decimal("2500.00")),
        ],
    )
    def test_parse(self, text, amount):
        parsed = parse_kes(text)
        assert parsed.valid
        assert parsed.amount == amount
        assert parsed.requires_confirmation is True

    def test_confirmation_required(self):
        parsed = parse_kes("500 bob")
        assert confirm_kes(parsed, Decimal("500.00"))
        assert not confirm_kes(parsed, Decimal("400.00"))

    def test_format_kes(self):
        assert format_kes(1500) == "KES 1,500.00"


class TestLanguageAndSheng:
    def test_english(self):
        guess = identify_kenya_language("I want to pay my account please")
        assert guess.language == KenyaLanguage.ENGLISH

    def test_kiswahili(self):
        guess = identify_kenya_language("nataka lipa salio asante")
        assert guess.language == KenyaLanguage.KISWAHILI

    def test_sheng(self):
        guess = identify_kenya_language("sasa boss poa fiti mambo vipi")
        assert guess.language == KenyaLanguage.SHENG

    def test_mixed(self):
        guess = identify_kenya_language("nataka to pay my balance sawa")
        assert guess.language == KenyaLanguage.MIXED

    def test_sheng_normalization_pipeline(self):
        turn = process_kenya_turn("sasa boss")
        assert turn.original_transcript == "sasa boss"
        assert turn.normalized_transcript


class TestEntitiesAndIntents:
    def test_entity_extraction(self):
        text = (
            "My name is Jane Wanjiku, send 500 bob to 0712345678, "
            "order ORD-99, account LOAN-1, QH12AB34CD, Kayole estate, "
            "national id 12345678 tomorrow 3pm"
        )
        entities = extract_kenyan_entities(text)
        assert entities.phone and entities.phone["e164"] == "+254712345678"
        assert entities.customer_name and "Jane" in entities.customer_name
        assert entities.amount_kes and entities.amount_kes["valid"]
        assert entities.order_number == "ORD-99"
        assert entities.account_number == "LOAN-1"
        assert entities.mpesa_transaction_code == "QH12AB34CD"
        assert entities.estate
        safe = entities.to_safe_dict()
        assert "12345678" not in str(safe.get("national_id_ref", ""))

    def test_pipeline_intents(self):
        cases = {
            "nataka kulipa": BusinessIntent.PAYMENT,
            "nataka balance yangu": BusinessIntent.BALANCE_INQUIRY,
            "weka miadi": BusinessIntent.BOOKING,
            "clinic appointment": BusinessIntent.APPOINTMENT,
            "where is my delivery": BusinessIntent.DELIVERY,
            "check my order": BusinessIntent.ORDER,
            "ninalalamika": BusinessIntent.COMPLAINT,
            "nataka mtu": BusinessIntent.ESCALATION,
            "namba ya akaunti": BusinessIntent.ACCOUNT_INQUIRY,
            "uko wapi": BusinessIntent.LOCATION_INQUIRY,
            "cancel my order": BusinessIntent.CANCELLATION,
            "sawa nimekubali": BusinessIntent.CONFIRMATION,
        }
        for text, intent in cases.items():
            turn = process_kenya_turn(text)
            assert turn.intent is not None
            assert turn.intent.intent == intent, (text, turn.intent.intent)


class TestTimezoneAndHours:
    def test_eat_formatting(self):
        utc = datetime(2026, 6, 1, 9, 0, tzinfo=ZoneInfo("UTC"))
        assert format_kenya_datetime(utc) == "01/06/2026 12:00"

    def test_config_timezone(self):
        ctx = build_kenya_context()
        assert ctx.timezone == "Africa/Nairobi"
        assert ctx.currency == "KES"
        assert ctx.iso_country_code == "KE"

    def test_weekday_hours(self):
        noon = datetime(2026, 6, 22, 12, 0, tzinfo=ZoneInfo(KENYA.timezone))
        sunday = datetime(2026, 6, 21, 12, 0, tzinfo=ZoneInfo(KENYA.timezone))
        assert is_within_business_hours(noon) is True
        assert is_within_business_hours(sunday) is False

    def test_madaraka_holiday(self):
        assert is_kenya_public_holiday(datetime(2026, 6, 1).date()) is True
        assert is_within_business_hours(
            datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo(KENYA.timezone))
        ) is False

    def test_attach_context_idempotent(self):
        first = attach_kenya_context({"foo": 1})
        second = attach_kenya_context(first)
        assert first["kenya_context"]["timezone"] == KENYA.timezone
        assert second["foo"] == 1
        assert "kenya_context" in second


class TestDuplicateContacts:
    async def test_local_and_e164_are_same_customer(self, db_session, async_session):
        org = OrganizationModel(provider_id="test-org-kenya-phone")
        async_session.add(org)
        await async_session.flush()
        crm = get_customer_service()
        first = await crm.create_customer(
            organization_id=org.id,
            phone_e164="0712345678",
            full_name="Amina Otieno",
        )
        second = await crm.create_customer(
            organization_id=org.id,
            phone_e164="+254712345678",
            full_name="Amina Otieno",
        )
        assert first.id == second.id
        assert first.phone_e164 == "+254712345678"
        assert first.metadata.get("phone_original") == "0712345678"
