import hashlib
import math
from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = 1
VEHICLE_PROFILE = "2022-kia-ev6-gt-line-hda2"
DETECTION_CLEAR_SECONDS = 0.5
POST_DETECTION_SECONDS = 8.0


def anonymized_route_id(route_name: str, salt: str) -> str:
  return hashlib.sha256(f"{salt}:{route_name}".encode()).hexdigest()[:20]


def _finite(value: Any, default: float = 0.0) -> float:
  try:
    result = float(value)
    return result if math.isfinite(result) else default
  except (TypeError, ValueError):
    return default


@dataclass
class StopEvent:
  start_time: float
  initial_speed: float
  initial_stop_distance: float
  model_ref: str
  model_name: str
  lead_at_detection: bool
  last_detection_time: float
  detection_end_time: float | None = None
  detection_samples: int = 0
  max_confidence: float = 0.0
  minimum_speed: float = math.inf
  minimum_accel: float = math.inf
  first_brake_time: float | None = None
  stock_aeb_seen: bool = False
  lead_seen: bool = False


@dataclass
class RouteSummaryBuilder:
  route_id: str
  firmware_commit: str = "unknown"
  firmware_branch: str = "unknown"
  first_time: float | None = None
  last_time: float | None = None
  last_car_time: float | None = None
  last_speed: float = 0.0
  distance_m: float = 0.0
  latest_lead: bool = False
  active_event: StopEvent | None = None
  events: list[dict[str, Any]] = field(default_factory=list)
  model_refs: set[str] = field(default_factory=set)

  def _observe_time(self, mono_time: float) -> None:
    self.first_time = mono_time if self.first_time is None else min(self.first_time, mono_time)
    self.last_time = mono_time if self.last_time is None else max(self.last_time, mono_time)

  def consume_car_state(self, mono_time: float, msg: Any) -> None:
    self._observe_time(mono_time)
    speed = max(0.0, _finite(getattr(msg, "vEgo", 0.0)))
    accel = _finite(getattr(msg, "aEgo", 0.0))
    if self.last_car_time is not None:
      dt = min(max(mono_time - self.last_car_time, 0.0), 1.0)
      self.distance_m += 0.5 * (self.last_speed + speed) * dt
    self.last_car_time = mono_time
    self.last_speed = speed

    if self.active_event is not None:
      event = self.active_event
      event.minimum_speed = min(event.minimum_speed, speed)
      event.minimum_accel = min(event.minimum_accel, accel)
      event.stock_aeb_seen |= bool(getattr(msg, "stockAeb", False))
      if bool(getattr(msg, "brakePressed", False)) and event.first_brake_time is None:
        event.first_brake_time = mono_time
      self._maybe_finish_event(mono_time)

  def consume_radar_state(self, mono_time: float, msg: Any) -> None:
    self._observe_time(mono_time)
    self.latest_lead = bool(getattr(getattr(msg, "leadOne", None), "status", False))
    if self.active_event is not None:
      self.active_event.lead_seen |= self.latest_lead

  def consume_plan(self, mono_time: float, msg: Any) -> None:
    self._observe_time(mono_time)
    alerts = msg.e2eAlerts
    detected = bool(alerts.stopIntentDetected)
    model_ref = str(alerts.modelRef or "default")
    model_name = str(alerts.modelName or "Default Model")
    self.model_refs.add(model_ref)

    if detected:
      if self.active_event is None:
        self.active_event = StopEvent(
          start_time=mono_time,
          initial_speed=self.last_speed,
          initial_stop_distance=_finite(alerts.stopDistance),
          model_ref=model_ref,
          model_name=model_name,
          lead_at_detection=self.latest_lead,
          last_detection_time=mono_time,
          minimum_speed=self.last_speed,
        )
      event = self.active_event
      event.last_detection_time = mono_time
      event.detection_end_time = None
      event.detection_samples += 1
      event.max_confidence = max(event.max_confidence, _finite(alerts.stopIntentConfidence))
    elif self.active_event is not None:
      event = self.active_event
      if event.detection_end_time is None and mono_time - event.last_detection_time >= DETECTION_CLEAR_SECONDS:
        event.detection_end_time = mono_time
      self._maybe_finish_event(mono_time)

  def _maybe_finish_event(self, mono_time: float, force: bool = False) -> None:
    event = self.active_event
    if event is None:
      return
    ready = event.detection_end_time is not None and mono_time - event.detection_end_time >= POST_DETECTION_SECONDS
    if not force and not ready:
      return

    end_time = mono_time
    minimum_speed = event.initial_speed if math.isinf(event.minimum_speed) else event.minimum_speed
    minimum_accel = 0.0 if math.isinf(event.minimum_accel) else event.minimum_accel
    brake_delay = None if event.first_brake_time is None else max(0.0, event.first_brake_time - event.start_time)
    if minimum_speed <= 0.5:
      outcome = "stopped"
    elif brake_delay is not None:
      outcome = "driver_braked"
    elif event.initial_speed > 0.0 and minimum_speed <= event.initial_speed * 0.5:
      outcome = "slowed_substantially"
    else:
      outcome = "unresolved"

    base_time = self.first_time or event.start_time
    self.events.append({
      "start_offset_s": round(event.start_time - base_time, 2),
      "observation_duration_s": round(max(0.0, end_time - event.start_time), 2),
      "initial_speed_mps": round(event.initial_speed, 3),
      "minimum_speed_mps": round(minimum_speed, 3),
      "minimum_accel_mps2": round(minimum_accel, 3),
      "predicted_stop_distance_m": round(event.initial_stop_distance, 2),
      "max_heuristic_confidence": round(event.max_confidence, 3),
      "detection_samples": event.detection_samples,
      "model_ref": event.model_ref,
      "model_name": event.model_name,
      "radar_lead_at_detection": event.lead_at_detection,
      "radar_lead_seen_during_response": event.lead_seen,
      "driver_brake_delay_s": None if brake_delay is None else round(brake_delay, 2),
      "stock_aeb_reported": event.stock_aeb_seen,
      "outcome": outcome,
    })
    self.active_event = None

  def finalize(self, segment_count: int) -> dict[str, Any]:
    if self.active_event is not None:
      self._maybe_finish_event(self.last_time or self.active_event.last_detection_time, force=True)
    duration = 0.0 if self.first_time is None or self.last_time is None else max(0.0, self.last_time - self.first_time)
    return {
      "schema_version": SCHEMA_VERSION,
      "route_id": self.route_id,
      "vehicle_profile": VEHICLE_PROFILE,
      "firmware": {"commit": self.firmware_commit, "branch": self.firmware_branch},
      "source_segments": segment_count,
      "duration_s": round(duration, 2),
      "distance_km": round(self.distance_m / 1000.0, 3),
      "model_refs": sorted(self.model_refs),
      "stop_intent_event_count": len(self.events),
      "stop_intent_events": self.events,
      "privacy": {
        "route_name_hashed": True,
        "gps_excluded": True,
        "video_excluded": True,
        "vin_excluded": True,
        "dongle_id_excluded": True,
      },
    }
