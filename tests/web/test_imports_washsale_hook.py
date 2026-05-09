"""Test that the imports commit flow enqueues washsale_watch."""

from unittest.mock import MagicMock as MM

from net_alpha.web.routes.imports import _enqueue_washsale_watch


def test_enqueue_washsale_watch_with_no_scheduler_is_noop():
    request = MM()
    request.app.state.scheduler = None
    _enqueue_washsale_watch(request)  # must not raise


def test_enqueue_washsale_watch_with_scheduler_adds_job():
    request = MM()
    request.app.state.scheduler = MM()
    request.app.state.service_state = MM()
    request.app.state.repository = MM()
    _enqueue_washsale_watch(request)
    request.app.state.scheduler.add_job.assert_called_once()


def test_enqueue_washsale_watch_missing_service_state_is_noop():
    request = MM()
    request.app.state.scheduler = MM()
    request.app.state.service_state = None
    request.app.state.repository = MM()
    _enqueue_washsale_watch(request)
    request.app.state.scheduler.add_job.assert_not_called()


def test_enqueue_washsale_watch_missing_repository_is_noop():
    request = MM()
    request.app.state.scheduler = MM()
    request.app.state.service_state = MM()
    request.app.state.repository = None
    _enqueue_washsale_watch(request)
    request.app.state.scheduler.add_job.assert_not_called()
