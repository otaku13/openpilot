import base64
import json
import re
from collections.abc import Callable

import requests


GITHUB_API = "https://api.github.com"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GithubSummaryUploader:
  def __init__(self, repository: str, token: str, upload_allowed: Callable[[], bool], session=None):
    if not REPO_PATTERN.fullmatch(repository):
      raise ValueError("GitHub repository must use owner/name format")
    self.repository = repository
    self.token = token
    self.upload_allowed = upload_allowed
    self.session = session or requests.Session()

  @property
  def headers(self) -> dict[str, str]:
    return {
      "Accept": "application/vnd.github+json",
      "Authorization": f"Bearer {self.token}",
      "X-GitHub-Api-Version": "2022-11-28",
    }

  def upload(self, route_id: str, summary: dict) -> bool:
    if not self.upload_allowed():
      return False

    path = f"drives/{route_id}.json"
    url = f"{GITHUB_API}/repos/{self.repository}/contents/{path}"
    content = json.dumps(summary, indent=2, sort_keys=True).encode()
    payload = {
      "message": f"data: add sanitized EV6 route {route_id}",
      "content": base64.b64encode(content).decode(),
    }
    response = self.session.put(url, headers=self.headers, json=payload, timeout=20)
    if response.status_code in (200, 201):
      return True
    if response.status_code == 422:
      existing = self.session.get(url, headers=self.headers, timeout=20)
      return existing.status_code == 200
    return False
