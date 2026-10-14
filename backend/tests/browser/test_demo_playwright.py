# ruff: noqa: E402, I001
"""Opt-in browser acceptance tests for the local receipt demo.

Run with PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 and a seeded test account.
The suite is skipped when Playwright is not installed, so the normal backend
test suite remains dependency-light.
"""

import os
import base64

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
    expect(page.get_by_role("button", name="Extract Receipt Data")).to_be_visible()
    expect(page.locator("#review")).to_be_hidden()


def test_failed_login_is_reported(page):
    page.goto(f"{BASE_URL}/demo")
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password").fill("wrong-password-123")
    page.get_by_role("button", name="Log in").click()
    expect(page.locator("#loginStatus")).to_contain_text("failed")


def test_upload_review_save_and_approve(page):
    login(page)
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
    page.get_by_label("Receipt image").set_input_files({"name": "receipt.png", "mimeType": "image/png", "buffer": png})
    with page.expect_response("**/predict") as upload_response:
        page.get_by_role("button", name="Extract Receipt Data").click()
    uploaded = upload_response.value.json()
    expect(page.locator("#status")).to_contain_text("completed", timeout=30000)
    expect(page.locator("#review")).to_be_visible()
    expect(page.locator("#mode")).to_contain_text("MOCK EXTRACTION")
    company = page.get_by_label("Correction for Company")
    company.fill("Browser Corrected Cafe")
    expect(page.get_by_role("button", name="Approve and create expense")).to_be_disabled()
    page.get_by_role("button", name="Save Corrections").click()
    expect(page.locator("#message")).to_contain_text("Corrections saved")
    expect(page.get_by_text("corrected", exact=True)).to_be_visible()
    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Approve and create expense").click()
    expect(page.locator("#message")).to_contain_text("Approved; expense created")
    page.get_by_label("Open receipt by ID").fill(uploaded["receipt_id"])
    page.get_by_role("button", name="Open receipt").click()
    expect(page.locator("#preview")).to_be_visible()


def test_upload_and_reject(page):
    login(page)
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
    page.get_by_label("Receipt image").set_input_files({"name": "reject.png", "mimeType": "image/png", "buffer": png})
    page.get_by_role("button", name="Extract Receipt Data").click()
    expect(page.locator("#status")).to_contain_text("completed", timeout=30000)
    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Reject").click()
    expect(page.locator("#message")).to_contain_text("Receipt rejected")


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
