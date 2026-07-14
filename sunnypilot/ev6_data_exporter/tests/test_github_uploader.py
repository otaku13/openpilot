from types import SimpleNamespace

import pytest

from openpilot.sunnypilot.ev6_data_exporter.github_uploader import GithubSummaryUploader


class FakeSession:
  def __init__(self, put_status=201, get_status=200):
    self.put_status = put_status
    self.get_status = get_status
    self.put_calls = []
    self.get_calls = []

  def put(self, *args, **kwargs):
    self.put_calls.append((args, kwargs))
    return SimpleNamespace(status_code=self.put_status)

  def get(self, *args, **kwargs):
    self.get_calls.append((args, kwargs))
    return SimpleNamespace(status_code=self.get_status)


def test_upload_is_blocked_when_vehicle_state_disallows_network():
  session = FakeSession()
  uploader = GithubSummaryUploader("owner/repo", "secret-token", lambda: False, session)

  assert not uploader.upload("route-id", {"safe": True})
  assert not session.put_calls


def test_uploads_json_to_private_repository_contents_api():
  session = FakeSession()
  uploader = GithubSummaryUploader("owner/repo", "secret-token", lambda: True, session)

  assert uploader.upload("route-id", {"safe": True})
  args, kwargs = session.put_calls[0]
  assert args[0].endswith("/repos/owner/repo/contents/drives/route-id.json")
  assert kwargs["headers"]["Authorization"] == "Bearer secret-token"
  assert "secret-token" not in str(kwargs["json"])


def test_existing_route_is_treated_as_already_uploaded():
  session = FakeSession(put_status=422, get_status=200)
  uploader = GithubSummaryUploader("owner/repo", "secret-token", lambda: True, session)

  assert uploader.upload("route-id", {"safe": True})
  assert len(session.get_calls) == 1


@pytest.mark.parametrize("repository", ["", "missing-slash", "owner/repo/extra", "owner/re po"])
def test_rejects_invalid_repository_names(repository):
  with pytest.raises(ValueError):
    GithubSummaryUploader(repository, "token", lambda: True)
