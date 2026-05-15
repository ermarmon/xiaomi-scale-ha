# Xiaomi Scale HA

Custom integration for Xiaomi Mi Scale BLE advertisements using Home Assistant's
shared Bluetooth stack. This means local Bluetooth adapters and ESPHome Bluetooth
proxies can all provide advertisements to the integration.

## Install

Copy `custom_components/xiaomi_scale_ha` into your Home Assistant config folder:

```text
/config/custom_components/xiaomi_scale_ha
```

Restart Home Assistant, then add the integration from:

```text
Settings > Devices & services > Add integration > Xiaomi Scale HA
```

Home Assistant 2026.3+ loads the integration icon and logo from the local
`brand/` directory.

## Configuration

The setup flow asks for:

- Scale MAC address.
- Optional mobile notification service, for example `notify.mobile_app_your_phone`.
- Whether to create Home Assistant persistent notifications for pending measurements.
- Whether to send a mobile notification when a weight is registered.
- Seconds to wait for impedance before sending the registered-weight notification.
- Users JSON.

Example users JSON:

```json
[
  {
    "NAME": "User1",
    "GT": 50,
    "LT": 80,
    "SEX": "male",
    "HEIGHT": 175,
    "DOB": "1985-01-01",
    "NOTIFY_SERVICE": "notify.mobile_app_user1",
    "ALEXA_DEVICE": "media_player.echo_user1"
  }
]
```

`GT` and `LT` are the bootstrap weight range in kg. After a user has at least
three measurements, the integration matches future readings against that user's
recent history.

`NOTIFY_SERVICE` is optional per user. Registered-weight notifications for that
user go only to that service. Pending ambiguous measurements are sent only to the
candidate users' notification services. If a user has no `NOTIFY_SERVICE`, that
user does not receive a mobile notification.

`ALEXA_DEVICE` is optional per user. Alexa actionable notifications are disabled
by default. When enabled, pending ambiguous measurements ask each candidate on
their configured Echo device.

You can edit users later from the integration options:

```text
Settings > Devices & services > Xiaomi Scale HA > Configure
```

Saving options reloads the integration so newly added or removed users get their
sensor entities refreshed.

## Notes

The scale only needs BLE advertisements, so ESPHome Bluetooth proxies work with
`connectable: false`.

## Matching and pending measurements

When a stabilized measurement arrives:

- If exactly one user matches, the integration assigns the measurement and stores it
  in the user's history.
- If several users match, the measurement becomes pending.
- If no user matches, the measurement is ignored and logged.

For users with fewer than three measurements, matching uses the configured `GT` and
`LT` range. After that, it compares the new weight with the user's recent history.

The scale often sends a stable weight first and then sends another advertisement
with impedance a few seconds later. The integration updates the sensor as soon as
the weight arrives, but delays the registered-weight notification for
`impedance_wait_seconds` so it can include impedance-based metrics when available.
If the user steps off before impedance is measured, the weight-only notification
is still sent after the wait window.

## Notifications

Pending measurements can create:

- A persistent notification in Home Assistant.
- A mobile actionable notification if a candidate user has `NOTIFY_SERVICE`.
- A confirmation notification when a weight is registered, if enabled in options.
- An Alexa actionable question if Alexa actions are enabled and candidate users
  have `ALEXA_DEVICE` configured.

Mobile actions are handled by listening for the `mobile_app_notification_action`
event and assigning or discarding the pending measurement automatically.

Alexa actionable notifications require the external Alexa Actions setup by
keatontaylor and a script compatible with `script.activate_alexa_actionable_notification`.
The integration calls that script with:

- `text`
- `event_id`
- `alexa_device`
- `suppress_confirmation`

It listens for `alexa_actionable_notification`. A `ResponseYes` assigns the
pending measurement to that user; `ResponseNo` keeps the pending measurement
available for another candidate or manual assignment.

## Services

The integration registers these actions:

- `xiaomi_scale_ha.assign_pending`
- `xiaomi_scale_ha.discard_pending`
- `xiaomi_scale_ha.send_pending_notification`
- `xiaomi_scale_ha.clear_history`
- `xiaomi_scale_ha.delete_history_measurement`

`entry_id` is optional when only one scale is configured.

### History maintenance

The diagnostic `history` entity shows the stored recent measurements per user.
The last stored measurement is restored on integration startup so user weight
sensors do not become unknown just because Home Assistant restarted.

The diagnostic `last BLE measurement` entity starts as `listening` after the
Bluetooth callbacks are registered. If it stays there, the integration is loaded
but has not received a matching advertisement from the configured scale yet.

Clear one user's history:

```yaml
action: xiaomi_scale_ha.clear_history
data:
  user_name: Ernes
```

Clear all history:

```yaml
action: xiaomi_scale_ha.clear_history
data: {}
```

Delete the latest stored measurement for one user:

```yaml
action: xiaomi_scale_ha.delete_history_measurement
data:
  user_name: Ernes
  index: -1
```

## Events

The integration fires these events:

- `xiaomi_scale_ha_pending_measurement`
- `xiaomi_scale_ha_measurement_assigned`
- `xiaomi_scale_ha_measurement_discarded`
