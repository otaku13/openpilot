from collections import defaultdict
from pathlib import Path


def completed_routes(log_root: Path) -> dict[str, list[Path]]:
  routes: dict[str, list[Path]] = defaultdict(list)
  if not log_root.is_dir():
    return routes
  for segment in log_root.iterdir():
    if not segment.is_dir() or "--" not in segment.name:
      continue
    if any(path.name.endswith(".lock") for path in segment.iterdir()):
      continue
    route_name, segment_number = segment.name.rsplit("--", 1)
    if segment_number.isdigit() and (segment / "rlog.zst").is_file():
      routes[route_name].append(segment)
  for segments in routes.values():
    segments.sort(key=lambda path: int(path.name.rsplit("--", 1)[1]))
  return routes
