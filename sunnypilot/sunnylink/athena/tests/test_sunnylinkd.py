"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.sunnypilot.sunnylink.athena import sunnylinkd


class TestSunnylinkdMethods:
  def setup_method(self):
    self.saved_params = []

    self.original_save = sunnylinkd.save_param_from_base64_encoded_string

    def mock_save_param(key, value, compression=False):
      self.saved_params.append((key, value, compression))

    sunnylinkd.save_param_from_base64_encoded_string = mock_save_param

  def teardown_method(self):
    sunnylinkd.save_param_from_base64_encoded_string = self.original_save

  def test_saveParams_blocked(self):
    blocked_params = {
      "Ev6DataGithubToken": "github_pat_secret",
      "Ev6DataHashSalt": "private-salt",
      "GithubUsername": "attacker",
      "GithubSshKeys": "ssh-rsa attacker_key",
    }

    sunnylinkd.saveParams(blocked_params)

    assert len(self.saved_params) == 0

  def test_ev6_secrets_are_private_and_blocked(self):
    assert {"Ev6DataGithubToken", "Ev6DataHashSalt"} <= sunnylinkd.PRIVATE_PARAMS
    assert sunnylinkd.PRIVATE_PARAMS <= sunnylinkd.BLOCKED_PARAMS

  def test_saveParams_allowed(self):
    allowed_params = {
      "SpeedLimitOffset": "5",
      "MyCustomParam": "123"
    }

    sunnylinkd.saveParams(allowed_params)

    # verify content
    assert len(self.saved_params) == 2
    keys_saved = [p[0] for p in self.saved_params]
    assert "SpeedLimitOffset" in keys_saved
    assert "MyCustomParam" in keys_saved

  def test_saveParams_mixed(self):
    mixed_params = {
      "GithubUsername": "attacker",
      "SpeedLimitOffset": "10"
    }

    sunnylinkd.saveParams(mixed_params)

    # should save allowed one
    assert len(self.saved_params) == 1
    assert self.saved_params[0][0] == "SpeedLimitOffset"
    assert self.saved_params[0][1] == "10"
