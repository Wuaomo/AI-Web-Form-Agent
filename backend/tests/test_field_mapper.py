"""Tests for LLM-assisted field mapping and its safety fallback."""

import json
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, LlmApiUsageLog, Profile, Task, WorkflowMemoryItem
from app.services.field_mapper import (
    _build_llm_prompt,
    _request_deepseek_mapping,
    map_fields_with_llm,
    map_fields_with_llm_result,
)
from app.services.workflow_memory import build_field_memory_text
from app.workflow_constants import MEMORY_TYPE_CONFIRMED_MAPPING


class LLMFieldMapperTests(unittest.TestCase):
    """Exercise successful mappings, invalid output, and action rejection."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        profile = Profile(
            profile_name="Test profile",
            full_name="Ada Lovelace",
            email="ada@example.com",
        )
        task = Task(
            url="https://example.com/form",
            profile=profile,
            status="MAPPING_READY",
        )
        self.db.add(task)
        self.db.commit()
        self.task_id = task.id

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _add_field(
        self,
        *,
        label: str,
        selector: str,
        field_type: str = "text",
        task_id: int | None = None,
    ) -> FormField:
        field = FormField(
            task_id=task_id or self.task_id,
            label=label,
            selector=selector,
            field_type=field_type,
            required=False,
        )
        self.db.add(field)
        self.db.commit()
        return field

    def test_llm_maps_label_that_rules_do_not_recognize(self) -> None:
        field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": field.id,
                        "mapped_profile_key": "email",
                        "confidence": 0.93,
                    }
                ]
            }
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value=llm_json,
        ):
            mapped = map_fields_with_llm(self.task_id, self.db)

        self.assertEqual(mapped[0].mapped_profile_key, "email")
        self.assertEqual(mapped[0].mapped_value, "ada@example.com")
        self.assertEqual(mapped[0].confidence, 0.93)

    def test_reuses_cached_mapping_for_same_form_without_provider_call(self) -> None:
        first_field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        first_llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": first_field.id,
                        "mapped_profile_key": "email",
                        "confidence": 0.93,
                    }
                ]
            }
        )

        second_profile = Profile(
            profile_name="Second profile",
            full_name="Grace Hopper",
            email="grace@example.com",
        )
        second_task = Task(
            url="https://example.com/form",
            profile=second_profile,
            status="MAPPING_READY",
        )
        self.db.add(second_task)
        self.db.commit()
        second_field = self._add_field(
            task_id=second_task.id,
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        second_llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": second_field.id,
                        "mapped_profile_key": "email",
                        "confidence": 0.93,
                    }
                ]
            }
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            side_effect=[first_llm_json, second_llm_json],
        ) as request_mapping:
            first_mapping = map_fields_with_llm(
                self.task_id,
                self.db,
                provider="deepseek",
            )
            second_mapping = map_fields_with_llm(
                second_task.id,
                self.db,
                provider="deepseek",
            )

        self.assertEqual(request_mapping.call_count, 1)
        self.assertEqual(first_mapping[0].mapped_value, "ada@example.com")
        self.assertEqual(second_mapping[0].id, second_field.id)
        self.assertEqual(second_mapping[0].mapped_profile_key, "email")
        self.assertEqual(second_mapping[0].mapped_value, "grace@example.com")
        self.assertEqual(second_mapping[0].confidence, 0.93)

    def test_llm_prompt_keeps_task_specific_data_after_cacheable_prefix(self) -> None:
        first_field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        second_profile = Profile(
            profile_name="Second profile",
            full_name="Grace Hopper",
            email="grace@example.com",
        )
        second_task = Task(
            url="https://example.com/form",
            profile=second_profile,
            status="MAPPING_READY",
        )
        self.db.add(second_task)
        self.db.commit()
        second_field = self._add_field(
            task_id=second_task.id,
            label="Where should we send updates?",
            selector="#contact-destination",
        )

        first_prompt = _build_llm_prompt(
            [first_field],
            {"full_name": "Ada Lovelace", "email": "ada@example.com"},
        )
        second_prompt = _build_llm_prompt(
            [second_field],
            {"full_name": "Grace Hopper", "email": "grace@example.com"},
        )
        marker = "\nCurrent run field id map:\n"

        self.assertIn(marker, first_prompt)
        self.assertEqual(
            first_prompt.split(marker)[0],
            second_prompt.split(marker)[0],
        )
        stable_fields_section = first_prompt.split("Stable form fields:\n")[1].split(
            marker
        )[0]
        self.assertNotIn('"field_id"', stable_fields_section)
        self.assertIn(f'"field_id": {first_field.id}', first_prompt)
        self.assertIn(f'"field_id": {second_field.id}', second_prompt)

    def test_llm_prompt_has_long_stable_prefix_across_different_forms(self) -> None:
        email_field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        phone_field = self._add_field(
            label="Best number to reach you",
            selector="#phone-number",
            field_type="tel",
        )

        email_prompt = _build_llm_prompt(
            [email_field],
            {"full_name": "Ada Lovelace", "email": "ada@example.com"},
        )
        phone_prompt = _build_llm_prompt(
            [phone_field],
            {"full_name": "Grace Hopper", "phone": "+1 555 0101"},
        )
        marker = "Stable form fields:\n"

        self.assertEqual(
            email_prompt.split(marker)[0],
            phone_prompt.split(marker)[0],
        )
        self.assertGreater(len(email_prompt.split(marker)[0]), 2500)

    def test_llm_prompt_includes_historical_examples_when_provided(self) -> None:
        field = self._add_field(label="GitHub profile", selector="#github")
        prompt = _build_llm_prompt(
            [field],
            {"full_name": "Ada Lovelace", "github": "https://github.com/ada"},
            retrieved_examples=[
                {
                    "field_text": 'label: GitHub; placeholder: profile link',
                    "mapped_profile_key": "github",
                    "mapped_value": "should_not_leak",
                }
            ],
        )

        self.assertIn("Historical mapping examples:", prompt)
        self.assertIn('-> profile key: github', prompt)
        self.assertNotIn("should_not_leak", prompt)

    def test_llm_prompt_omits_historical_examples_when_empty(self) -> None:
        field = self._add_field(label="GitHub profile", selector="#github")
        prompt = _build_llm_prompt(
            [field],
            {"full_name": "Ada Lovelace", "github": "https://github.com/ada"},
            retrieved_examples=[],
        )

        self.assertNotIn("Historical mapping examples:", prompt)

    def test_retrieval_fallback_sets_profile_key_when_llm_and_rules_miss(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        field = self._add_field(label="Portfolio URL", selector="#portfolio", field_type="url")

        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_portfolio",
            field_text=build_field_memory_text(field),
            mapped_profile_key="github",
            success_count=10,
        )
        self.db.add(memory_item)
        self.db.commit()

        llm_json = json.dumps({"mappings": []})
        with patch("app.services.field_mapper._request_llm_mapping", return_value=llm_json):
            result = map_fields_with_llm_result(self.task_id, self.db, provider="deepseek")

        mapped_by_id = {mapped.id: mapped for mapped in result.fields}
        self.assertEqual(mapped_by_id[field.id].mapped_profile_key, "github")

    def test_retrieval_fallback_does_not_override_existing_mapping(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        field = self._add_field(label="Contact destination", selector="#contact-destination")
        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_contact",
            field_text=build_field_memory_text(field),
            mapped_profile_key="github",
            success_count=10,
        )
        self.db.add(memory_item)
        self.db.commit()

        llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": field.id,
                        "mapped_profile_key": "email",
                        "confidence": 0.9,
                    }
                ]
            }
        )
        with patch("app.services.field_mapper._request_llm_mapping", return_value=llm_json):
            result = map_fields_with_llm_result(self.task_id, self.db, provider="deepseek")

        mapped_by_id = {mapped.id: mapped for mapped in result.fields}
        self.assertEqual(mapped_by_id[field.id].mapped_profile_key, "email")

    def test_retrieval_fallback_does_not_trigger_for_low_score(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        field = self._add_field(label="Portfolio URL", selector="#portfolio", field_type="url")
        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_low",
            field_text="label: Phone\nname: phone\ntype: tel\noptions: []",
            mapped_profile_key="github",
            success_count=1,
        )
        self.db.add(memory_item)
        self.db.commit()

        llm_json = json.dumps({"mappings": []})
        with patch("app.services.field_mapper._request_llm_mapping", return_value=llm_json):
            result = map_fields_with_llm_result(self.task_id, self.db, provider="deepseek")

        mapped_by_id = {mapped.id: mapped for mapped in result.fields}
        self.assertIsNone(mapped_by_id[field.id].mapped_profile_key)

    def test_retrieval_fallback_requires_rules_and_llm_to_miss(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        field = self._add_field(label="Email", selector="#email", field_type="email")
        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_email",
            field_text=build_field_memory_text(field),
            mapped_profile_key="github",
            success_count=10,
        )
        self.db.add(memory_item)
        self.db.commit()

        llm_json = json.dumps({"mappings": []})
        with patch("app.services.field_mapper._request_llm_mapping", return_value=llm_json):
            result = map_fields_with_llm_result(self.task_id, self.db, provider="deepseek")

        mapped_by_id = {mapped.id: mapped for mapped in result.fields}
        self.assertIsNone(mapped_by_id[field.id].mapped_profile_key)

    def test_memory_mode_off_disables_retrieval_examples_and_fallback(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        field = self._add_field(
            label="Portfolio URL",
            selector="#portfolio",
            field_type="url",
        )
        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_memory_off_portfolio",
            field_text=build_field_memory_text(field),
            mapped_profile_key="github",
            success_count=10,
        )
        self.db.add(memory_item)
        self.db.commit()

        captured_prompt: list[str] = []

        def fake_request(prompt: str, *_args, **_kwargs) -> str:
            captured_prompt.append(prompt)
            return json.dumps({"mappings": []})

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            side_effect=fake_request,
        ):
            result = map_fields_with_llm_result(
                self.task_id,
                self.db,
                provider="deepseek",
                memory_mode="off",
            )

        mapped_by_id = {mapped.id: mapped for mapped in result.fields}
        self.assertIsNone(mapped_by_id[field.id].mapped_profile_key)
        self.assertTrue(captured_prompt)
        self.assertNotIn("Historical mapping examples:", captured_prompt[0])

    def test_cached_empty_mapping_still_applies_memory_fallback(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        first_field = self._add_field(
            label="Portfolio URL",
            selector="#portfolio",
            field_type="url",
        )
        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_cached_portfolio",
            field_text=build_field_memory_text(first_field),
            mapped_profile_key="github",
            success_count=10,
        )
        self.db.add(memory_item)
        self.db.commit()

        empty_llm_json = json.dumps({"mappings": []})

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value=empty_llm_json,
        ) as request_mapping:
            first_result = map_fields_with_llm_result(
                self.task_id,
                self.db,
                provider="deepseek",
            )

        self.assertEqual(request_mapping.call_count, 1)
        self.assertEqual(first_result.fields[0].mapped_profile_key, "github")

        second_profile = Profile(
            profile_name="Cached profile",
            full_name="Grace Hopper",
            email="grace@example.com",
            github="https://github.com/grace",
        )
        second_task = Task(
            url="https://example.com/form",
            profile=second_profile,
            status="MAPPING_READY",
        )
        self.db.add(second_task)
        self.db.commit()
        second_field = self._add_field(
            task_id=second_task.id,
            label="Portfolio URL",
            selector="#portfolio",
            field_type="url",
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            side_effect=AssertionError("cache hit should skip provider call"),
        ):
            second_result = map_fields_with_llm_result(
                second_task.id,
                self.db,
                provider="deepseek",
                memory_mode="on",
            )

        mapped_by_id = {mapped.id: mapped for mapped in second_result.fields}
        self.assertEqual(mapped_by_id[second_field.id].mapped_profile_key, "github")
        self.assertEqual(
            mapped_by_id[second_field.id].mapped_value,
            "https://github.com/grace",
        )

    def test_exception_path_applies_memory_fallback_after_rules_miss(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        field = self._add_field(
            label="Portfolio URL",
            selector="#portfolio",
            field_type="url",
        )
        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_exception_portfolio",
            field_text=build_field_memory_text(field),
            mapped_profile_key="github",
            success_count=10,
        )
        self.db.add(memory_item)
        self.db.commit()

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            side_effect=RuntimeError("LLM request failed"),
        ):
            result = map_fields_with_llm_result(
                self.task_id,
                self.db,
                provider="deepseek",
            )

        self.assertTrue(result.used_fallback)
        mapped_by_id = {mapped.id: mapped for mapped in result.fields}
        self.assertEqual(mapped_by_id[field.id].mapped_profile_key, "github")

    def test_exception_path_does_not_override_rules_hit_with_memory_fallback(self) -> None:
        task = self.db.get(Task, self.task_id)
        assert task is not None
        task.profile.github = "https://github.com/ada"
        self.db.commit()

        field = self._add_field(
            label="Email",
            selector="#email",
            field_type="email",
        )
        memory_item = WorkflowMemoryItem(
            memory_type=MEMORY_TYPE_CONFIRMED_MAPPING,
            workflow_type="form_fill",
            source_domain="example.com",
            field_signature="sig_exception_email",
            field_text=build_field_memory_text(field),
            mapped_profile_key="github",
            success_count=10,
        )
        self.db.add(memory_item)
        self.db.commit()

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            side_effect=RuntimeError("LLM request failed"),
        ):
            result = map_fields_with_llm_result(
                self.task_id,
                self.db,
                provider="deepseek",
            )

        self.assertTrue(result.used_fallback)
        mapped_by_id = {mapped.id: mapped for mapped in result.fields}
        self.assertEqual(mapped_by_id[field.id].mapped_profile_key, "email")

    def test_llm_maps_split_name_fields_from_full_name(self) -> None:
        first_name = self._add_field(
            label="Given name",
            selector="#FirstName",
        )
        last_name = self._add_field(
            label="Family name",
            selector="#LastName",
        )
        llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": first_name.id,
                        "mapped_profile_key": "first_name",
                        "confidence": 0.95,
                    },
                    {
                        "field_id": last_name.id,
                        "mapped_profile_key": "last_name",
                        "confidence": 0.95,
                    },
                ]
            }
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value=llm_json,
        ):
            mapped = map_fields_with_llm(self.task_id, self.db)

        mapped_by_id = {field.id: field for field in mapped}
        self.assertEqual(
            mapped_by_id[first_name.id].mapped_profile_key,
            "first_name",
        )
        self.assertEqual(mapped_by_id[first_name.id].mapped_value, "Ada")
        self.assertEqual(
            mapped_by_id[last_name.id].mapped_profile_key,
            "last_name",
        )
        self.assertEqual(mapped_by_id[last_name.id].mapped_value, "Lovelace")

    def test_llm_skips_profile_keys_without_values(self) -> None:
        email_field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        github_field = self._add_field(
            label="Show us your code portfolio",
            selector="#portfolio-link",
            field_type="url",
        )
        llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": email_field.id,
                        "mapped_profile_key": "email",
                        "confidence": 0.93,
                    },
                    {
                        "field_id": github_field.id,
                        "mapped_profile_key": "github",
                        "confidence": 0.9,
                    },
                ]
            }
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value=llm_json,
        ):
            mapped = map_fields_with_llm(self.task_id, self.db)

        mapped_by_id = {field.id: field for field in mapped}
        self.assertEqual(mapped_by_id[email_field.id].mapped_profile_key, "email")
        self.assertEqual(mapped_by_id[email_field.id].mapped_value, "ada@example.com")
        self.assertIsNone(mapped_by_id[github_field.id].mapped_profile_key)
        self.assertIsNone(mapped_by_id[github_field.id].mapped_value)

    def test_invalid_json_falls_back_to_rule_mapping(self) -> None:
        self._add_field(label="Contact Email", selector="#contact-email")

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value="not valid JSON",
        ):
            mapped = map_fields_with_llm(self.task_id, self.db)

        self.assertEqual(mapped[0].mapped_profile_key, "email")
        self.assertEqual(mapped[0].mapped_value, "ada@example.com")

    def test_llm_mapping_result_reports_used_fallback_false_on_success(self) -> None:
        field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": field.id,
                        "mapped_profile_key": "email",
                        "confidence": 0.93,
                    }
                ]
            }
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value=llm_json,
        ):
            result = map_fields_with_llm_result(self.task_id, self.db)

        self.assertEqual(result.used_fallback, False)
        self.assertEqual(result.fields[0].mapped_profile_key, "email")

    def test_llm_mapping_result_reports_used_fallback_true_on_exception(self) -> None:
        self._add_field(label="Contact Email", selector="#contact-email")

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            side_effect=RuntimeError("LLM request failed"),
        ):
            result = map_fields_with_llm_result(self.task_id, self.db)

        self.assertEqual(result.used_fallback, True)
        self.assertEqual(result.fields[0].mapped_profile_key, "email")

    def test_action_or_submit_mapping_is_rejected(self) -> None:
        email_field = self._add_field(
            label="Email Address",
            selector="#email",
            field_type="email",
        )
        submit_field = self._add_field(
            label="Submit application",
            selector="#submit",
            field_type="submit",
        )
        unsafe_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": submit_field.id,
                        "mapped_profile_key": "email",
                        "confidence": 1,
                        "action": "click",
                    }
                ]
            }
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value=unsafe_json,
        ):
            mapped = map_fields_with_llm(self.task_id, self.db)

        mapped_by_id = {field.id: field for field in mapped}
        self.assertEqual(
            mapped_by_id[email_field.id].mapped_profile_key,
            "email",
        )
        self.assertIsNone(mapped_by_id[submit_field.id].mapped_profile_key)
        self.assertIsNone(mapped_by_id[submit_field.id].mapped_value)

    def test_file_upload_mapping_is_rejected(self) -> None:
        upload_field = self._add_field(
            label="Resume",
            selector="input[name='resume']",
            field_type="file",
        )
        unsafe_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": upload_field.id,
                        "mapped_profile_key": "email",
                        "confidence": 1,
                    }
                ]
            }
        )

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            return_value=unsafe_json,
        ):
            mapped = map_fields_with_llm(self.task_id, self.db)

        self.assertIsNone(mapped[0].mapped_profile_key)
        self.assertIsNone(mapped[0].mapped_value)

    def test_deepseek_provider_routes_mapping_request(self) -> None:
        field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        llm_json = json.dumps(
            {
                "mappings": [
                    {
                        "field_id": field.id,
                        "mapped_profile_key": "email",
                        "confidence": 0.92,
                    }
                ]
            }
        )

        with (
            patch("app.services.field_mapper.config.LLM_PROVIDER", "deepseek"),
            patch(
                "app.services.field_mapper._request_deepseek_mapping",
                return_value=llm_json,
            ) as deepseek,
        ):
            mapped = map_fields_with_llm(self.task_id, self.db)

        deepseek.assert_called_once()
        self.assertEqual(mapped[0].mapped_profile_key, "email")
        self.assertEqual(mapped[0].mapped_value, "ada@example.com")

    def test_deepseek_request_uses_chat_completion_api(self) -> None:
        response = {
            "usage": {
                "prompt_tokens": 979,
                "completion_tokens": 197,
                "total_tokens": 1176,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 979,
            },
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "mappings": [
                                    {
                                        "field_id": 1,
                                        "mapped_profile_key": "email",
                                        "confidence": 0.9,
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        }

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch("app.services.field_mapper.config.DEEPSEEK_MODEL", "deepseek-v4-flash"),
            patch("app.services.field_mapper._post_json", return_value=response) as post_json,
        ):
            result = _request_deepseek_mapping("Map this field")

        post_json.assert_called_once()
        url, payload, headers = post_json.call_args.args
        self.assertEqual(url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(result, response["choices"][0]["message"]["content"])

    def test_deepseek_request_logs_usage_statistics(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "mappings": [
                                    {
                                        "field_id": 1,
                                        "mapped_profile_key": "email",
                                        "confidence": 0.9,
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125,
                "prompt_cache_hit_tokens": 60,
                "prompt_cache_miss_tokens": 40,
            },
        }

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch("app.services.field_mapper._post_json", return_value=response),
            patch("app.services.field_mapper.logger.info") as log_info,
        ):
            _request_deepseek_mapping("Map this field")

        log_info.assert_called_once()
        message, usage_json = log_info.call_args.args
        self.assertEqual(message, "DeepSeek API usage: %s")
        usage_data = json.loads(usage_json)
        self.assertEqual(usage_data["provider"], "deepseek")
        self.assertEqual(usage_data["model"], "deepseek-v4-flash")
        self.assertEqual(usage_data["prompt_tokens"], 100)
        self.assertEqual(usage_data["completion_tokens"], 25)
        self.assertEqual(usage_data["total_tokens"], 125)
        self.assertEqual(usage_data["cache_hit_tokens"], 60)
        self.assertEqual(usage_data["cache_miss_tokens"], 40)
        self.assertTrue(usage_data["cache_hit"])
        self.assertEqual(usage_data["cache_hit_rate"], 0.6)
        self.assertIn("latency_ms", usage_data)
        self.assertIn("cache_source", usage_data)
        self.assertEqual(usage_data["cache_source"], "provider_prompt_cache")

    def test_deepseek_request_persists_usage_statistics(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "mappings": [
                                    {
                                        "field_id": 1,
                                        "mapped_profile_key": "email",
                                        "confidence": 0.9,
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 40,
            },
        }

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch("app.services.field_mapper._post_json", return_value=response),
        ):
            _request_deepseek_mapping(
                "Map this field",
                task_id=self.task_id,
                db=self.db,
            )

        usage_log = self.db.scalar(
            select(LlmApiUsageLog).where(
                LlmApiUsageLog.task_id == self.task_id
            )
        )
        self.assertIsNotNone(usage_log)
        self.assertEqual(usage_log.provider, "deepseek")
        self.assertEqual(usage_log.model, "deepseek-v4-flash")
        self.assertEqual(usage_log.prompt_tokens, 120)
        self.assertEqual(usage_log.completion_tokens, 30)
        self.assertEqual(usage_log.total_tokens, 150)
        self.assertEqual(usage_log.cache_hit_tokens, 80)
        self.assertEqual(usage_log.cache_miss_tokens, 40)
        self.assertTrue(usage_log.cache_hit)
        self.assertEqual(usage_log.cache_hit_rate, 80 / 120)

    def test_deepseek_request_records_latency_ms(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "mappings": [
                                    {
                                        "field_id": 1,
                                        "mapped_profile_key": "email",
                                        "confidence": 0.9,
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 100,
            },
        }

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch("app.services.field_mapper._post_json", return_value=response),
        ):
            _request_deepseek_mapping(
                "Map this field",
                task_id=self.task_id,
                db=self.db,
            )

        usage_log = self.db.scalar(
            select(LlmApiUsageLog).where(
                LlmApiUsageLog.task_id == self.task_id
            )
        )
        self.assertIsNotNone(usage_log)
        self.assertGreaterEqual(usage_log.latency_ms, 0)
        self.assertIsNone(usage_log.error_type)
        self.assertFalse(usage_log.fallback_used)
        self.assertEqual(usage_log.cache_source, "no_cache")

    def test_deepseek_request_records_provider_prompt_cache_hit(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "mappings": [
                                    {
                                        "field_id": 1,
                                        "mapped_profile_key": "email",
                                        "confidence": 0.9,
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125,
                "prompt_cache_hit_tokens": 75,
                "prompt_cache_miss_tokens": 25,
            },
        }

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch("app.services.field_mapper._post_json", return_value=response),
        ):
            _request_deepseek_mapping(
                "Map this field",
                task_id=self.task_id,
                db=self.db,
            )

        usage_log = self.db.scalar(
            select(LlmApiUsageLog).where(
                LlmApiUsageLog.task_id == self.task_id
            )
        )
        self.assertIsNotNone(usage_log)
        self.assertEqual(usage_log.cache_source, "provider_prompt_cache")
        self.assertTrue(usage_log.cache_hit)

    def test_deepseek_request_records_error_on_exception(self) -> None:
        self._add_field(label="Contact Email", selector="#contact-email")

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch(
                "app.services.field_mapper._post_json",
                side_effect=TimeoutError("API timeout"),
            ),
        ):
            result = map_fields_with_llm_result(self.task_id, self.db, provider="deepseek")

        self.assertTrue(result.used_fallback)

        usage_logs = self.db.scalars(
            select(LlmApiUsageLog).where(
                LlmApiUsageLog.task_id == self.task_id
            )
        ).all()
        self.assertEqual(len(usage_logs), 1)
        usage_log = usage_logs[0]
        self.assertEqual(usage_log.error_type, "TimeoutError")
        self.assertTrue(usage_log.fallback_used)
        self.assertGreaterEqual(usage_log.latency_ms, 0)
        self.assertEqual(usage_log.cache_source, "no_cache")

    def test_fallback_path_records_fallback_used_true(self) -> None:
        self._add_field(label="Contact Email", selector="#contact-email")

        with patch(
            "app.services.field_mapper._request_llm_mapping",
            side_effect=RuntimeError("LLM request failed"),
        ):
            result = map_fields_with_llm_result(self.task_id, self.db)

        self.assertTrue(result.used_fallback)

        usage_log = self.db.scalar(
            select(LlmApiUsageLog).where(
                LlmApiUsageLog.task_id == self.task_id
            )
        )
        self.assertIsNotNone(usage_log)
        self.assertTrue(usage_log.fallback_used)
        self.assertEqual(usage_log.error_type, "RuntimeError")

    def test_app_mapping_cache_hit_does_not_create_provider_usage_log(self) -> None:
        first_field = self._add_field(
            label="Where should we send updates?",
            selector="#contact-destination",
        )
        provider_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "mappings": [
                                    {
                                        "field_id": first_field.id,
                                        "mapped_profile_key": "email",
                                        "confidence": 0.93,
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 100,
            },
        }

        second_profile = Profile(
            profile_name="Second profile",
            full_name="Grace Hopper",
            email="grace@example.com",
        )
        second_task = Task(
            url="https://example.com/form",
            profile=second_profile,
            status="MAPPING_READY",
        )
        self.db.add(second_task)
        self.db.commit()
        second_field = self._add_field(
            task_id=second_task.id,
            label="Where should we send updates?",
            selector="#contact-destination",
        )

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch(
                "app.services.field_mapper._post_json",
                return_value=provider_response,
            ) as mock_post,
        ):
            map_fields_with_llm(
                self.task_id,
                self.db,
                provider="deepseek",
            )
            map_fields_with_llm(
                second_task.id,
                self.db,
                provider="deepseek",
            )

            mock_post.assert_called_once()

        usage_logs = list(
            self.db.scalars(
                select(LlmApiUsageLog).where(
                    LlmApiUsageLog.task_id == second_task.id
                )
            )
        )
        self.assertEqual(len(usage_logs), 0)

        first_task_usage_logs = list(
            self.db.scalars(
                select(LlmApiUsageLog).where(
                    LlmApiUsageLog.task_id == self.task_id
                )
            )
        )
        self.assertEqual(len(first_task_usage_logs), 1)

    def test_provider_prompt_cache_hit_recorded_in_usage_log(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "mappings": [
                                    {
                                        "field_id": 1,
                                        "mapped_profile_key": "email",
                                        "confidence": 0.9,
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 25,
                "total_tokens": 125,
                "prompt_cache_hit_tokens": 75,
                "prompt_cache_miss_tokens": 25,
            },
        }

        with (
            patch("app.services.field_mapper.config.DEEPSEEK_API_KEY", "test-key"),
            patch("app.services.field_mapper._post_json", return_value=response),
        ):
            _request_deepseek_mapping(
                "Map this field",
                task_id=self.task_id,
                db=self.db,
            )

        usage_log = self.db.scalar(
            select(LlmApiUsageLog).where(
                LlmApiUsageLog.task_id == self.task_id
            )
        )
        self.assertIsNotNone(usage_log)
        self.assertEqual(usage_log.cache_source, "provider_prompt_cache")
        self.assertTrue(usage_log.cache_hit)
        self.assertEqual(usage_log.cache_hit_rate, 0.75)


if __name__ == "__main__":
    unittest.main()
