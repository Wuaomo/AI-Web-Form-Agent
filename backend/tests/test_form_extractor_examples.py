"""Regression tests for component-library form extraction examples."""

from pathlib import Path

from playwright.sync_api import sync_playwright

from app.services.form_extractor import _EXTRACT_FIELDS_SCRIPT


def test_extracts_taotian_social_resume_component_form() -> None:
    """Extract semantic fields from the Taotian-style Kuma/Uxcore mock page."""

    example_url = (
        Path("backend/examples/taotian-social-resume.html").resolve().as_uri()
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2200})
        page.goto(example_url, wait_until="domcontentloaded")
        fields = page.locator(
            'input:not([type="hidden"]), textarea, select'
        ).evaluate_all(_EXTRACT_FIELDS_SCRIPT)
        browser.close()

    field_summaries = [
        (
            field["form_title"],
            field["label"],
            field["placeholder"],
            field["field_type"],
            field["required"],
        )
        for field in fields
    ]

    assert field_summaries == [
        ("个人信息", "姓名", "请输入", "text", True),
        ("个人信息", "手机", "请输入", "text", True),
        ("个人信息", "邮箱", "请输入", "text", True),
        ("个人信息", "目前所在城市", "请输入", "text", False),
        ("个人信息", "期望工作城市", "请输入", "text", False),
        ("工作经历", "公司名称", "请输入", "text", True),
        ("工作经历", "职务", "请输入", "text", True),
        ("工作经历", "时间", "开始日期", "text", True),
        ("工作经历", "时间", "结束日期", "text", True),
        ("工作经历", "职务描述", "请输入", "textarea", True),
        ("项目经历", "项目名称", "请输入", "text", True),
        ("项目经历", "时间", "开始日期", "text", True),
        ("项目经历", "时间", "结束日期", "text", True),
        ("项目经历", "职责描述", "请输入", "textarea", True),
        ("教育情况", "学历", "请选择", "text", True),
        ("教育情况", "时间", "开始日期", "text", True),
        ("教育情况", "时间", "结束日期", "text", True),
        ("教育情况", "学校全称", "请输入", "text", True),
        ("教育情况", "专业", "请输入", "text", True),
        ("教育情况", "学校经历内容", "请输入", "textarea", True),
        (
            "声明条款",
            "申请此职位表明您已经阅读淘天有限公司及其关联公司《申请工作机会须知》相关内容",
            None,
            "checkbox",
            True,
        ),
    ]
