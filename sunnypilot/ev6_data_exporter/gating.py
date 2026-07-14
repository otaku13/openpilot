from typing import Any


def ev6_data_exporter_ready(started: bool, params: Any, CP: Any) -> bool:
  platform = str(CP.carFingerprint).lower()
  return not started and "ev6" in platform and params.get_bool("Ev6DataUploadEnabled") and not params.get_bool("NetworkMetered")
