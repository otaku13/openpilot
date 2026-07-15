# Kia EV6 stop-intent advisory

This branch adds an experimental, advisory-only warning for the 2022 Kia EV6 GT-Line HDA2. It does not identify a traffic
signal state directly. It watches the selected driving model's predicted trajectory and `shouldStop` output for sustained
stop intent that is not explained by a radar-tracked lead vehicle.

## Safety boundary

- Stock Kia longitudinal control and forward-collision/AEB behavior remain unchanged.
- The feature does not send brake, accelerator, cruise, or Hyundai ADAS CAN commands.
- The alert can be late, false, or absent. The driver must identify traffic controls and brake as needed.
- The feature never emits a green/go recommendation or determines that an intersection is safe to enter.

## EV6 baseline model

The initial baseline is **Pop Model (March 20, 2026)**, model reference
`6f71783a8a8faa07ddaeef5bbb6809b4f4f44a15`. The model name and reference are recorded in `longitudinalPlanSP.e2eAlerts`
with each detection so route logs can be compared against SC and WMI V12 later.

## Trigger guardrails

The warning requires all of the following for at least 0.8 seconds:

- feature toggle enabled;
- vehicle speed between 2.5 and 27 m/s;
- model `shouldStop` output asserted;
- predicted speed at or below 1 m/s between 5 and 120 meters ahead;
- no radar lead close enough to explain the predicted stop; and
- no current driver accelerator or brake input.

An eight-second cooldown and one-second clear interval prevent repeated alerts from a single prediction.

## Install on comma 3X

USB is not required. With the comma 3X connected to Wi-Fi, choose **Custom Software** after an uninstall/factory reset and
enter:

```text
installer.comma.ai/otaku13/sunnypilot/ev6
```

If this fork is already installed, use **Settings → Software → CHECK**, then select `ev6-red-light-advisory` as the target
branch, or `ev6` for the shorter alias. This is an experimental development branch rather than an official sunnypilot release; install it only for the
controlled EV6 testing described here. Keep the source firmware repository public so the device installer can retrieve it.

After installation, select **Pop Model (March 20, 2026)** and enable **Possible Stop Ahead Alert** under Visuals. Configure
the separate private summary uploader by following `docs/EV6_PRIVATE_DATA_EXPORT.md`.
