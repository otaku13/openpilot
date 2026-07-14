#!/usr/bin/env python3
import json
import os
import secrets
import time
from pathlib import Path

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.system.hardware.hw import Paths
from openpilot.tools.lib.logreader import LogReader
from openpilot.sunnypilot.ev6_data_exporter.github_uploader import GithubSummaryUploader
from openpilot.sunnypilot.ev6_data_exporter.routes import completed_routes
from openpilot.sunnypilot.ev6_data_exporter.summary import RouteSummaryBuilder, anonymized_route_id


SCAN_INTERVAL_SECONDS = 60
MAX_ROUTES_PER_PASS = 1
STATE_VERSION = 1


def exporter_root() -> Path:
  override = os.getenv("EV6_DATA_EXPORT_ROOT")
  return Path(override) if override else Path(Paths.log_root()).parent / "ev6-data-export"


def atomic_json_write(path: Path, data: dict) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  temporary = path.with_suffix(path.suffix + ".tmp")
  temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
  os.replace(temporary, path)


def extract_summary(route_id: str, segments: list[Path], params: Params) -> dict:
  builder = RouteSummaryBuilder(
    route_id=route_id,
    firmware_commit=str(params.get("GitCommit") or "unknown"),
    firmware_branch=str(params.get("GitBranch") or "unknown"),
  )
  services = {"carState", "radarState", "longitudinalPlanSP"}
  for segment in segments:
    for event in LogReader(str(segment / "rlog.zst"), only_union_types=True):
      service = event.which()
      if service not in services:
        continue
      mono_time = event.logMonoTime / 1e9
      if service == "carState":
        builder.consume_car_state(mono_time, event.carState)
      elif service == "radarState":
        builder.consume_radar_state(mono_time, event.radarState)
      elif service == "longitudinalPlanSP":
        builder.consume_plan(mono_time, event.longitudinalPlanSP)
  return builder.finalize(len(segments))


class Ev6DataExporter:
  def __init__(self, params=None, log_root=None, output_root=None):
    self.params = params or Params()
    self.log_root = Path(log_root or Paths.log_root())
    self.output_root = Path(output_root or exporter_root())
    self.state_path = self.output_root / "state.json"
    self.summary_root = self.output_root / "summaries"

  def _state(self) -> dict:
    try:
      state = json.loads(self.state_path.read_text())
      return state if state.get("version") == STATE_VERSION else {"version": STATE_VERSION, "uploaded": []}
    except (OSError, ValueError):
      return {"version": STATE_VERSION, "uploaded": []}

  def _salt(self) -> str:
    salt = self.params.get("Ev6DataHashSalt")
    if not salt:
      salt = secrets.token_hex(32)
      self.params.put("Ev6DataHashSalt", salt, block=True)
    return str(salt)

  def upload_allowed(self) -> bool:
    return self.params.get_bool("Ev6DataUploadEnabled") and not self.params.get_bool("IsOnroad") and \
           not self.params.get_bool("NetworkMetered")

  def run_once(self) -> int:
    token = self.params.get("Ev6DataGithubToken")
    repository = self.params.get("Ev6DataGithubRepo")
    if not token or not repository or not self.upload_allowed():
      return 0

    state = self._state()
    uploaded = set(state["uploaded"])
    uploader = GithubSummaryUploader(str(repository), str(token), self.upload_allowed)
    completed = 0
    for route_name, segments in sorted(completed_routes(self.log_root).items()):
      route_id = anonymized_route_id(route_name, self._salt())
      if route_id in uploaded:
        continue
      try:
        summary = extract_summary(route_id, segments, self.params)
        atomic_json_write(self.summary_root / f"{route_id}.json", summary)
        if not self.upload_allowed() or not uploader.upload(route_id, summary):
          break
        uploaded.add(route_id)
        state["uploaded"] = sorted(uploaded)
        atomic_json_write(self.state_path, state)
        completed += 1
        cloudlog.info("EV6 data exporter uploaded sanitized route %s", route_id)
      except Exception:
        cloudlog.exception("EV6 data exporter failed to process a route")
      if completed >= MAX_ROUTES_PER_PASS:
        break
    return completed


def main() -> None:
  exporter = Ev6DataExporter()
  while True:
    exporter.run_once()
    time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
  main()
