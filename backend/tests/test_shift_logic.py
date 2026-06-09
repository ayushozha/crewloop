"""Core-loop logic tests: reply classification, STOP compliance, roster CSV
parsing, at-risk flagging, and message templates."""
from datetime import UTC, datetime, timedelta

import pytest

from app.shift_logic import (
    classify_reply,
    invite_message,
    is_at_risk,
    normalize_phone,
    parse_roster_csv,
    ping_message,
)

NOW = datetime(2026, 6, 20, 18, 0, tzinfo=UTC)


class TestClassifyReply:
    @pytest.mark.parametrize(
        "body",
        ["STOP", "stop", " Stop ", "STOPALL", "stop all", "UNSUBSCRIBE", "QUIT", "END", "CANCEL", "opt out", "STOP."],
    )
    def test_exact_stop_keywords_opt_out(self, body):
        assert classify_reply(body) == "stop"

    @pytest.mark.parametrize(
        "body",
        [
            "please don't cancel my shift",
            "I had to stop by the venue, all good",
            "should I cancel the order?",
        ],
    )
    def test_stop_words_inside_sentences_do_not_opt_out(self, body):
        assert classify_reply(body) != "stop"

    @pytest.mark.parametrize("body", ["START", "start", "unstop", "opt in"])
    def test_start_keywords(self, body):
        assert classify_reply(body) == "start"

    @pytest.mark.parametrize(
        "body",
        ["yes", "YES!", "Yep, I'm in", "sure, what is it?", "confirmed", "I can take it", "works for me", "count me in"],
    )
    def test_yes(self, body):
        assert classify_reply(body) == "yes"

    @pytest.mark.parametrize(
        "body",
        ["no", "Nope", "can't make it", "sorry, I'm booked", "not available that day", "I'll pass"],
    )
    def test_no(self, body):
        assert classify_reply(body) == "no"

    @pytest.mark.parametrize(
        "body",
        ["maybe", "not sure yet", "depends on my other gig", "might be able to", "let me check my schedule"],
    )
    def test_maybe_beats_yes_and_no(self, body):
        assert classify_reply(body) == "maybe"

    @pytest.mark.parametrize("body", ["what's the address?", "who is this?", "", "   "])
    def test_questions_and_noise_are_other(self, body):
        assert classify_reply(body) == "other"

    def test_no_sorry_is_no_not_yes(self):
        assert classify_reply("no, sorry — sounds good though") == "no"


class TestNormalizePhone:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("4159929589", "+14159929589"),
            ("14159929589", "+14159929589"),
            ("+14159929589", "+14159929589"),
            ("(415) 992-9589", "+14159929589"),
            ("415.992.9589", "+14159929589"),
            ("+447911123456", "+447911123456"),
        ],
    )
    def test_valid(self, raw, expected):
        assert normalize_phone(raw) == expected

    @pytest.mark.parametrize("raw", ["", "12345", "not a phone", "+12", None])
    def test_invalid(self, raw):
        assert normalize_phone(raw or "") is None


class TestParseRosterCsv:
    def test_happy_path_with_aliases(self):
        csv_text = (
            "Name,Phone Number,Roles,Priority,Rate,Notes\n"
            "Maria Lopez,415-555-0101,bartender;server,1,32.50,team lead\n"
            "Devon Price,(415) 555-0102,server,2,,\n"
        )
        rows, errors = parse_roster_csv(csv_text)
        assert errors == []
        assert len(rows) == 2
        assert rows[0]["name"] == "Maria Lopez"
        assert rows[0]["phone"] == "+14155550101"
        assert rows[0]["skills"] == ["bartender", "server"]
        assert rows[0]["priority"] == 1
        assert rows[0]["hourly_rate"] == 32.50
        assert rows[1]["hourly_rate"] is None
        assert rows[1]["priority"] == 2

    def test_bad_rows_become_errors_not_silent_skips(self):
        csv_text = "name,phone\nGood Person,4155550103\nNo Phone,\n,4155550104\nBad Phone,123\n"
        rows, errors = parse_roster_csv(csv_text)
        assert len(rows) == 1
        assert len(errors) == 3

    def test_duplicate_phone_keeps_first(self):
        csv_text = "name,phone\nA,4155550105\nB,4155550105\n"
        rows, errors = parse_roster_csv(csv_text)
        assert len(rows) == 1
        assert rows[0]["name"] == "A"
        assert any("duplicate" in e for e in errors)

    def test_missing_required_columns(self):
        rows, errors = parse_roster_csv("first,last\nA,B\n")
        assert rows == []
        assert any("name and phone" in e for e in errors)

    def test_empty_input(self):
        rows, errors = parse_roster_csv("")
        assert rows == []
        assert errors


class TestAtRisk:
    def test_yes_with_unanswered_old_ping_is_at_risk(self):
        assert is_at_risk(
            status="yes",
            ping_48_sent_at=NOW - timedelta(hours=3),
            ping_4_sent_at=None,
            last_reply_at=NOW - timedelta(days=1),
            now=NOW,
        )

    def test_reply_after_ping_clears_risk(self):
        assert not is_at_risk(
            status="yes",
            ping_48_sent_at=NOW - timedelta(hours=3),
            ping_4_sent_at=None,
            last_reply_at=NOW - timedelta(hours=1),
            now=NOW,
        )

    def test_recent_ping_within_grace_is_not_at_risk(self):
        assert not is_at_risk(
            status="yes",
            ping_48_sent_at=NOW - timedelta(minutes=30),
            ping_4_sent_at=None,
            last_reply_at=None,
            now=NOW,
        )

    def test_confirmed_is_never_at_risk(self):
        assert not is_at_risk(
            status="confirmed",
            ping_48_sent_at=NOW - timedelta(hours=10),
            ping_4_sent_at=NOW - timedelta(hours=5),
            last_reply_at=None,
            now=NOW,
        )

    def test_no_ping_sent_is_not_at_risk(self):
        assert not is_at_risk(
            status="yes", ping_48_sent_at=None, ping_4_sent_at=None, last_reply_at=None, now=NOW
        )

    def test_latest_ping_wins(self):
        # The T-4 ping was answered late; risk is judged against the newest ping.
        assert is_at_risk(
            status="yes",
            ping_48_sent_at=NOW - timedelta(hours=44),
            ping_4_sent_at=NOW - timedelta(hours=3),
            last_reply_at=NOW - timedelta(hours=40),
            now=NOW,
        )


class TestMessages:
    JOB = {
        "business_name": "Golden Gate Catering",
        "role": "server",
        "location": "SoMa, SF",
        "start_time": "Sat 6:00 PM",
        "end_time": "11:00 PM",
        "pay_amount": 150,
    }

    def test_invite_carries_stop_notice(self):
        msg = invite_message(self.JOB)
        assert "Reply STOP to opt out" in msg
        assert "YES" in msg and "NO" in msg
        assert "Golden Gate Catering" in msg
        assert "$150" in msg

    def test_ping_asks_for_confirmation(self):
        msg = ping_message(self.JOB, "48 hours")
        assert "Reply YES to confirm" in msg
        assert "48 hours" in msg
