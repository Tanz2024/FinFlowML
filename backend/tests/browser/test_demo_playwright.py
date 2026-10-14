# ruff: noqa: E402, I001
"""Opt-in browser acceptance tests for the local receipt demo.

Run with PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 and a seeded test account.
The suite is skipped when Playwright is not installed, so the normal backend
test suite remains dependency-light.
"""

import os

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402


BASE_URL = os.environ.get("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("PLAYWRIGHT_EMAIL", "test@example.com")
PASSWORD = os.environ.get("PLAYWRIGHT_PASSWORD", "test-password-123")


@pytest.fixture()
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture()
def browser():
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        yield browser
        browser.close()


def login(page):
    page.goto(f"{BASE_URL}/demo")
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Log in").click()
    expect(page.locator("#app")).to_be_visible()


def test_login_and_review_controls(page):
    login(page)
    expect(page.get_by_role("button", name="Save Corrections")).to_be_visible()
    expect(page.get_by_role("button", name="Approve and create expense")).to_be_disabled()


def test_unsaved_edits_disable_approval(page):
    login(page)
    # Supply a receipt ID through the environment for an already queued/reviewed receipt.
    receipt_id = os.environ.get("PLAYWRIGHT_RECEIPT_ID")
    if not receipt_id:
        pytest.skip("set PLAYWRIGHT_RECEIPT_ID to run review-state browser tests")
    page.get_by_label("Open receipt by ID").fill(receipt_id)
    page.get_by_role("button", name="Open receipt").click()
    expect(page.locator("#review")).to_be_visible()
    page.get_by_label("Correction for Company").fill("Changed for test")
    expect(page.get_by_role("button", name="Approve and create expense")).to_be_disabled()
    expect(page.locator("#unsaved")).to_be_visible()
