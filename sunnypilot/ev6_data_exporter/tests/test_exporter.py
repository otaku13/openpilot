from pathlib import Path

from openpilot.sunnypilot.ev6_data_exporter.routes import completed_routes


def make_segment(root: Path, route: str, number: int, locked=False, has_log=True):
  segment = root / f"{route}--{number}"
  segment.mkdir()
  if has_log:
    (segment / "rlog.zst").touch()
  if locked:
    (segment / "rlog.lock").touch()
  return segment


def test_completed_routes_groups_orders_and_skips_locked_segments(tmp_path):
  make_segment(tmp_path, "route-a", 1)
  make_segment(tmp_path, "route-a", 0)
  make_segment(tmp_path, "route-b", 0, locked=True)
  make_segment(tmp_path, "route-c", 0, has_log=False)

  routes = completed_routes(tmp_path)

  assert list(routes) == ["route-a"]
  assert [path.name for path in routes["route-a"]] == ["route-a--0", "route-a--1"]
