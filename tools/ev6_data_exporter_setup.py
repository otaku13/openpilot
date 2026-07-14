#!/usr/bin/env python3
import argparse
import getpass
import sys

import requests

from openpilot.common.params import Params


DEFAULT_REPOSITORY = "otaku13/ev6-driving-data"


def validate_access(repository: str, token: str) -> bool:
  response = requests.get(
    f"https://api.github.com/repos/{repository}",
    headers={
      "Accept": "application/vnd.github+json",
      "Authorization": f"Bearer {token}",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    timeout=20,
  )
  if response.status_code != 200:
    return False
  permissions = response.json().get("permissions", {})
  return bool(permissions.get("push"))


def main() -> int:
  parser = argparse.ArgumentParser(description="Configure private EV6 summary uploads")
  parser.add_argument("--repo", default=DEFAULT_REPOSITORY, help="Private GitHub repository in owner/name format")
  parser.add_argument("--disable", action="store_true", help="Disable uploads and remove the stored token")
  parser.add_argument("--status", action="store_true", help="Show configuration status without exposing the token")
  parser.add_argument("--skip-validation", action="store_true", help="Save configuration without testing GitHub access")
  args = parser.parse_args()
  params = Params()

  if args.status:
    print(f"enabled: {params.get_bool('Ev6DataUploadEnabled')}")
    print(f"repository: {params.get('Ev6DataGithubRepo') or DEFAULT_REPOSITORY}")
    print(f"token configured: {bool(params.get('Ev6DataGithubToken'))}")
    return 0

  if args.disable:
    params.put_bool("Ev6DataUploadEnabled", False, block=True)
    params.remove("Ev6DataGithubToken")
    print("EV6 private data uploads disabled; stored token removed.")
    return 0

  token = getpass.getpass("Fine-grained GitHub token: ")
  if not token:
    print("No token supplied.", file=sys.stderr)
    return 1
  if not args.skip_validation and not validate_access(args.repo, token):
    print("Token cannot push to the requested private repository.", file=sys.stderr)
    return 1

  params.put("Ev6DataGithubRepo", args.repo, block=True)
  params.put("Ev6DataGithubToken", token, block=True)
  params.put_bool("Ev6DataUploadEnabled", True, block=True)
  print(f"EV6 sanitized uploads enabled for {args.repo}.")
  print("The exporter runs only while offroad and on an unmetered network.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
