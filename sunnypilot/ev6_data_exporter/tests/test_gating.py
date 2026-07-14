from types import SimpleNamespace

import pytest

from openpilot.sunnypilot.ev6_data_exporter.gating import ev6_data_exporter_ready


class FakeParams:
  def __init__(self, enabled=True, metered=False):
    self.values = {"Ev6DataUploadEnabled": enabled, "NetworkMetered": metered}

  def get_bool(self, key):
    return self.values[key]


@pytest.mark.parametrize(("started", "platform", "enabled", "metered", "expected"), [
  (False, "KIA EV6 2022", True, False, True),
  (True, "KIA EV6 2022", True, False, False),
  (False, "KIA EV6 2022", False, False, False),
  (False, "KIA EV6 2022", True, True, False),
  (False, "HYUNDAI IONIQ 5", True, False, False),
])
def test_process_gate(started, platform, enabled, metered, expected):
  CP = SimpleNamespace(carFingerprint=platform)

  assert ev6_data_exporter_ready(started, FakeParams(enabled, metered), CP) is expected
