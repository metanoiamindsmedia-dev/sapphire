"""Tests for scheduler timezone handling (get_merged_timeline naive datetime fix)."""
import pytest
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo


class TestMergedTimelineTimezones:
    """get_merged_timeline must handle both naive and aware timestamps."""

    def _make_scheduler(self, activity, tasks=None):
        from core.continuity.scheduler import ContinuityScheduler
        with patch.object(ContinuityScheduler, '__init__', lambda self: None):
            sched = ContinuityScheduler()
            sched._activity = activity
            sched._tasks = {}
            sched._lock = threading.Lock()
            sched._sleep_ranges = []
            if tasks:
                sched._tasks = {t['id']: t for t in tasks}
        return sched

    def test_naive_timestamp_no_crash(self):
        """Naive datetime strings should not cause TypeError vs aware cutoff."""
        activity = [
            {"timestamp": "2026-03-10T10:00:00", "task_id": "t1", "action": "fired",
             "task_name": "test", "status": "ok"},
        ]
        sched = self._make_scheduler(activity)

        with patch('core.continuity.scheduler._user_now') as mock_now:
            mock_now.return_value = datetime(2026, 3, 10, 12, 0, 0, tzinfo=ZoneInfo('America/New_York'))
            result = sched.get_merged_timeline()

        assert 'past' in result

    def test_aware_timestamp_works(self):
        """Aware datetime strings should work normally."""
        activity = [
            {"timestamp": "2026-03-10T10:00:00+00:00", "task_id": "t1", "action": "fired",
             "task_name": "test", "status": "ok"},
        ]
        sched = self._make_scheduler(activity)

        with patch('core.continuity.scheduler._user_now') as mock_now:
            mock_now.return_value = datetime(2026, 3, 10, 12, 0, 0, tzinfo=ZoneInfo('UTC'))
            result = sched.get_merged_timeline()

        assert len(result['past']) == 1

    def test_old_timestamps_filtered_out(self):
        """Timestamps older than 24h should be excluded."""
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        recent_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        activity = [
            {"timestamp": old_ts, "task_id": "t1", "action": "fired",
             "task_name": "old", "status": "ok"},
            {"timestamp": recent_ts, "task_id": "t2", "action": "fired",
             "task_name": "recent", "status": "ok"},
        ]
        sched = self._make_scheduler(activity)

        with patch('core.continuity.scheduler._user_now') as mock_now:
            mock_now.return_value = datetime.now(ZoneInfo('UTC'))
            result = sched.get_merged_timeline()

        assert len(result['past']) == 1

    def test_invalid_timestamp_skipped(self):
        """Malformed timestamps should be silently skipped."""
        activity = [
            {"timestamp": "not-a-date", "task_id": "t1", "action": "fired",
             "task_name": "bad", "status": "ok"},
            {"timestamp": "2026-03-10T10:00:00+00:00", "task_id": "t2", "action": "fired",
             "task_name": "good", "status": "ok"},
        ]
        sched = self._make_scheduler(activity)

        with patch('core.continuity.scheduler._user_now') as mock_now:
            mock_now.return_value = datetime(2026, 3, 10, 12, 0, 0, tzinfo=ZoneInfo('UTC'))
            result = sched.get_merged_timeline()

        assert len(result['past']) == 1

    def test_mixed_naive_and_aware(self):
        """Mix of naive and aware timestamps should all be handled without crash."""
        activity = [
            {"timestamp": "2026-03-10T10:00:00", "task_id": "t1", "action": "a",
             "task_name": "naive", "status": "ok"},
            {"timestamp": "2026-03-10T10:00:00+00:00", "task_id": "t2", "action": "b",
             "task_name": "utc", "status": "ok"},
            {"timestamp": "2026-03-10T10:00:00-04:00", "task_id": "t3", "action": "c",
             "task_name": "est", "status": "ok"},
        ]
        sched = self._make_scheduler(activity)

        with patch('core.continuity.scheduler._user_now') as mock_now:
            mock_now.return_value = datetime(2026, 3, 10, 16, 0, 0, tzinfo=ZoneInfo('UTC'))
            result = sched.get_merged_timeline()

        assert 'past' in result
