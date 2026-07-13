from types import SimpleNamespace

import pytest

from cereal import custom
from openpilot.common.realtime import DT_MDL
from openpilot.sunnypilot.selfdrive.controls.lib.e2e_alerts_helper import (
  E2EAlertsHelper,
  STOP_INTENT_CLEAR_SECONDS,
  STOP_INTENT_TRIGGER_SECONDS,
)


class FakeParams:
  def __init__(self, stop_intent_enabled=True):
    self.stop_intent_enabled = stop_intent_enabled

  def get_bool(self, key):
    return self.stop_intent_enabled if key == "StopIntentAlert" else False


def make_sm(*, v_ego=13.0, should_stop=True, stop_distance=30.0, lead=False, lead_distance=100.0,
            gas_pressed=False, brake_pressed=False):
  model = SimpleNamespace(
    position=SimpleNamespace(x=[0.0, stop_distance / 2, stop_distance, stop_distance + 0.5]),
    velocity=SimpleNamespace(x=[v_ego, v_ego / 2, 0.8, 0.0]),
    action=SimpleNamespace(shouldStop=should_stop),
  )
  car_state = SimpleNamespace(vEgo=v_ego, gasPressed=gas_pressed, brakePressed=brake_pressed, standstill=False)
  car_control = SimpleNamespace(enabled=False)
  radar_state = SimpleNamespace(leadOne=SimpleNamespace(status=lead, dRel=lead_distance))
  return {'modelV2': model, 'carState': car_state, 'carControl': car_control, 'radarState': radar_state}


def update_for(helper, sm, seconds):
  alerts = []
  for _ in range(round(seconds / DT_MDL)):
    helper._update_stop_intent(sm)
    alerts.append(helper.stop_intent_alert)
  return alerts


def test_sustained_unexplained_stop_triggers_once():
  helper = E2EAlertsHelper(FakeParams())
  sm = make_sm()

  alerts = update_for(helper, sm, STOP_INTENT_TRIGGER_SECONDS)

  assert alerts.count(True) == 1
  assert alerts[-1]
  assert helper.stop_intent_detected
  assert helper.stop_intent_confidence == pytest.approx(1.0)
  assert helper.stop_distance == pytest.approx(30.0)
  assert not any(update_for(helper, sm, 1.0))


@pytest.mark.parametrize("blocked_sm", [
  make_sm(lead=True, lead_distance=25.0),
  make_sm(brake_pressed=True),
  make_sm(gas_pressed=True),
  make_sm(should_stop=False),
  make_sm(v_ego=2.0),
  make_sm(v_ego=28.0),
  make_sm(stop_distance=4.0),
  make_sm(stop_distance=121.0),
])
def test_guardrails_block_alert(blocked_sm):
  helper = E2EAlertsHelper(FakeParams())

  assert not any(update_for(helper, blocked_sm, STOP_INTENT_TRIGGER_SECONDS + 0.5))
  assert not helper.stop_intent_detected
  assert helper.stop_intent_confidence == 0.0


def test_disabled_by_default_toggle():
  helper = E2EAlertsHelper(FakeParams(stop_intent_enabled=False))

  assert not any(update_for(helper, make_sm(), STOP_INTENT_TRIGGER_SECONDS + 0.5))


def test_requires_clear_interval_before_rearming():
  helper = E2EAlertsHelper(FakeParams())
  candidate = make_sm()
  clear = make_sm(should_stop=False)
  update_for(helper, candidate, STOP_INTENT_TRIGGER_SECONDS)

  update_for(helper, clear, STOP_INTENT_CLEAR_SECONDS - DT_MDL)
  assert helper.stop_intent_latched

  update_for(helper, clear, DT_MDL)
  assert not helper.stop_intent_latched


def test_mismatched_model_arrays_are_rejected():
  helper = E2EAlertsHelper(FakeParams())
  sm = make_sm()
  sm['modelV2'].velocity.x.pop()

  assert not any(update_for(helper, sm, STOP_INTENT_TRIGGER_SECONDS + 0.5))
  assert helper.stop_distance == 0.0


def test_full_update_emits_advisory_chime_event():
  helper = E2EAlertsHelper(FakeParams())
  sm = make_sm()
  events = SimpleNamespace(added=[], add=lambda event: events.added.append(event))

  for _ in range(round(STOP_INTENT_TRIGGER_SECONDS / DT_MDL)):
    helper.update(sm, events)

  assert custom.OnroadEventSP.EventName.e2eChime in events.added
