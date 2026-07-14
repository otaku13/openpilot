from types import SimpleNamespace

from openpilot.sunnypilot.ev6_data_exporter.summary import RouteSummaryBuilder, anonymized_route_id


def plan(detected, distance=35.0, confidence=1.0):
  return SimpleNamespace(e2eAlerts=SimpleNamespace(
    stopIntentDetected=detected,
    stopDistance=distance,
    stopIntentConfidence=confidence,
    modelRef="6f71783a8a8faa07ddaeef5bbb6809b4f4f44a15",
    modelName="Pop Model (March 20, 2026)",
  ))


def car(speed, accel=0.0, brake=False, stock_aeb=False):
  return SimpleNamespace(vEgo=speed, aEgo=accel, brakePressed=brake, stockAeb=stock_aeb)


def radar(lead=False):
  return SimpleNamespace(leadOne=SimpleNamespace(status=lead))


def test_route_id_is_stable_salted_and_non_reversible():
  route_name = "2026-07-14--private-route-name"
  first = anonymized_route_id(route_name, "salt-a")

  assert first == anonymized_route_id(route_name, "salt-a")
  assert first != anonymized_route_id(route_name, "salt-b")
  assert route_name not in first
  assert len(first) == 20


def test_builds_sanitized_stop_response_summary():
  builder = RouteSummaryBuilder("anonymous-route", firmware_commit="abc123", firmware_branch="ev6-red-light-advisory")
  builder.consume_car_state(100.0, car(12.0))
  builder.consume_radar_state(100.1, radar(False))
  builder.consume_plan(101.0, plan(True, confidence=0.8))
  builder.consume_plan(101.5, plan(True))
  builder.consume_car_state(102.0, car(10.0, accel=-2.0, brake=True))
  builder.consume_plan(102.1, plan(False))
  builder.consume_car_state(104.0, car(0.2, accel=-1.0, stock_aeb=True))
  builder.consume_plan(110.5, plan(False))
  summary = builder.finalize(segment_count=2)

  assert summary["route_id"] == "anonymous-route"
  assert summary["stop_intent_event_count"] == 1
  assert summary["privacy"] == {
    "route_name_hashed": True,
    "gps_excluded": True,
    "video_excluded": True,
    "vin_excluded": True,
    "dongle_id_excluded": True,
  }
  event = summary["stop_intent_events"][0]
  assert event["outcome"] == "stopped"
  assert event["driver_brake_delay_s"] == 1.0
  assert event["stock_aeb_reported"]
  assert event["model_ref"].startswith("6f71783")
  serialized = str(summary).lower()
  assert "latitude" not in serialized
  assert "longitude" not in serialized
  assert "vin" not in serialized.replace("vin_excluded", "")


def test_radar_lead_status_is_preserved_for_analysis():
  builder = RouteSummaryBuilder("anonymous-route")
  builder.consume_car_state(10.0, car(8.0))
  builder.consume_radar_state(10.1, radar(True))
  builder.consume_plan(11.0, plan(True))
  summary = builder.finalize(segment_count=1)

  assert summary["stop_intent_events"][0]["radar_lead_at_detection"]
