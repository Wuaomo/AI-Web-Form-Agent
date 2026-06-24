"""Tests for LLM-assisted field mapping and its safety fallback."""

import json
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import FormField, Profile, Task
from app.services.field_mapper import _request_deepseek_mapping, map_fields_with_llm


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
    ) -> FormField:
        field = FormField(
            task_id=self.task_id,
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


if __name__ == "__main__":
    unittest.main()
