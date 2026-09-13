"""Tests for main.py — digest formatting, sending, and the dry-run mode."""
import os
from datetime import date
from unittest.mock import MagicMock, patch

from main import format_digest_html, format_digest_text, main, send_digest
from catalyst.models import ATS, Level, Posting, Sector
from catalyst.pipeline import PipelineResult


def _make_posting(**overrides):
    defaults = dict(
        employer="Acme",
        title="Process Engineer",
        url="https://acme.com/jobs/1",
        location="Midland, MI",
        posted_date=None,
        first_seen=date.today(),
        sector=Sector.SPECIALTY_CHEM,
        level=Level.EXPERIENCED,
        score=3.0,
        tags=["process engineer"],
        raw={},
    )
    defaults.update(overrides)
    return Posting(**defaults)


class TestFormatDigestHtml:
    def test_empty_list_says_no_postings(self):
        assert "No new postings" in format_digest_html([])

    def test_contains_title_employer_location_score_tags(self):
        posting = _make_posting()
        html = format_digest_html([posting])
        assert "Process Engineer" in html
        assert "Acme" in html
        assert "Midland, MI" in html
        assert "3.0" in html
        assert "process engineer" in html

    def test_deep_links_to_posting_url(self):
        posting = _make_posting(url="https://acme.com/jobs/42")
        html = format_digest_html([posting])
        assert 'href="https://acme.com/jobs/42"' in html

    def test_groups_by_sector(self):
        p1 = _make_posting(sector=Sector.SPECIALTY_CHEM, title="A")
        p2 = _make_posting(sector=Sector.ENERGY_STORAGE, title="B")
        html = format_digest_html([p1, p2])
        assert "SPECIALTY_CHEM" in html
        assert "ENERGY_STORAGE" in html

    def test_sorted_by_score_descending_within_group(self):
        low = _make_posting(title="Low", score=1.0)
        high = _make_posting(title="High", score=5.0)
        html = format_digest_html([low, high])
        assert html.index("High") < html.index("Low")

    def test_caps_at_40_with_more_line(self):
        postings = [_make_posting(title=f"Job {i}", score=float(i)) for i in range(45)]
        html = format_digest_html(postings)
        assert "+5 more" in html

    def test_no_more_line_when_under_cap(self):
        postings = [_make_posting(title=f"Job {i}") for i in range(5)]
        html = format_digest_html(postings)
        assert "more" not in html


class TestFormatDigestText:
    def test_empty_list(self):
        assert format_digest_text([]) == "No new postings today."

    def test_contains_key_fields(self):
        posting = _make_posting()
        text = format_digest_text([posting])
        assert "Process Engineer" in text
        assert "Acme" in text
        assert "Midland, MI" in text
        assert "https://acme.com/jobs/1" in text

    def test_caps_at_40_with_more_line(self):
        postings = [_make_posting(title=f"Job {i}") for i in range(41)]
        text = format_digest_text(postings)
        assert "+1 more" in text


def _make_smtp_mock():
    smtp_instance = MagicMock()
    smtp_cls = MagicMock()
    smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    return smtp_cls, smtp_instance


class TestSendDigest:
    def test_calls_smtp_login_with_password(self):
        smtp_cls, smtp_instance = _make_smtp_mock()
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_digest([_make_posting()])
        smtp_instance.login.assert_called_once_with("test@example.com", "secret")

    def test_calls_send_message(self):
        smtp_cls, smtp_instance = _make_smtp_mock()
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_digest([_make_posting()])
        smtp_instance.send_message.assert_called_once()

    def test_single_recipient_no_bcc(self):
        sent_msgs = []
        smtp_cls, smtp_instance = _make_smtp_mock()
        smtp_instance.send_message.side_effect = lambda msg: sent_msgs.append(msg)
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_digest([_make_posting()])
        assert sent_msgs, "send_message was not called"
        assert "Bcc" not in sent_msgs[0]
        assert sent_msgs[0]["To"] == "test@example.com"

    def test_subject_includes_count(self):
        sent_msgs = []
        smtp_cls, smtp_instance = _make_smtp_mock()
        smtp_instance.send_message.side_effect = lambda msg: sent_msgs.append(msg)
        with patch("main.smtplib.SMTP_SSL", smtp_cls), \
             patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "secret"}):
            send_digest([_make_posting(), _make_posting(title="Other")])
        assert "2" in sent_msgs[0]["Subject"]


class TestMain:
    def test_dry_run_does_not_send_email(self, capsys):
        result = PipelineResult(new=[_make_posting()], active=[_make_posting()])
        with patch("main.run", return_value=result) as mock_run, \
             patch("main.send_digest") as mock_send:
            main(dry_run=True)
        mock_send.assert_not_called()
        mock_run.assert_called_once_with(persist=False)

    def test_dry_run_prints_digest(self, capsys):
        result = PipelineResult(new=[_make_posting(title="Dry Run Job")], active=[])
        with patch("main.run", return_value=result):
            main(dry_run=True)
        captured = capsys.readouterr()
        assert "Dry Run Job" in captured.out

    def test_live_run_persists_and_sends_when_new_postings_exist(self):
        result = PipelineResult(new=[_make_posting()], active=[_make_posting()])
        with patch("main.run", return_value=result) as mock_run, \
             patch("main.send_digest") as mock_send:
            main(dry_run=False)
        mock_run.assert_called_once_with(persist=True)
        mock_send.assert_called_once_with(result.new)

    def test_live_run_skips_send_when_no_new_postings(self, capsys):
        result = PipelineResult(new=[], active=[])
        with patch("main.run", return_value=result), \
             patch("main.send_digest") as mock_send:
            main(dry_run=False)
        mock_send.assert_not_called()
