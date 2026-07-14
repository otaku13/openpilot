# Private EV6 driving-data export

The `ev6_data_exporter` process creates compact summaries from completed route logs and sends them to the private
`otaku13/ev6-driving-data` GitHub repository. It runs only while the car is offroad, the network is unmetered, and the
feature is explicitly enabled.

## Data included

- anonymized route ID derived from a private, device-local salt;
- firmware branch and commit;
- drive duration and approximate distance;
- selected driving-model name and reference;
- stop-intent distance and heuristic confirmation value;
- speed, deceleration, driver-brake response, radar-lead status, and reported stock-AEB state; and
- response classification such as stopped, driver braked, slowed, or unresolved.

No GPS coordinates, raw CAN, VIN, dongle ID, original route name, camera data, or driver-monitoring data are exported.
The original logs remain subject to the normal comma/sunnypilot retention and upload settings.

## GitHub token

Create a fine-grained personal access token scoped to only `otaku13/ev6-driving-data` with **Contents: Read and write**.
Do not put the token in a command, shell history, repository, issue, or chat message.

After installing this branch, SSH into the comma 3X and run:

```sh
cd /data/openpilot
python3 tools/ev6_data_exporter_setup.py
```

The script prompts for the token without echoing it, validates write access, and stores it in `Ev6DataGithubToken`. That
parameter is marked `DONT_LOG` and is excluded from settings backups.

Check status or disable and erase the token with:

```sh
python3 tools/ev6_data_exporter_setup.py --status
python3 tools/ev6_data_exporter_setup.py --disable
```

## Local state

Sanitized summaries and upload state are stored under `/data/media/0/ev6-data-export/`. A route is marked complete only
after GitHub confirms the upload, preventing accidental loss and duplicate commits.
