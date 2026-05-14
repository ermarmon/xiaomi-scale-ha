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

## Configuration

The setup flow asks for:

- Scale MAC address.
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
    "DOB": "1985-01-01"
  }
]
```

`GT` and `LT` are the bootstrap weight range in kg. After a user has at least
three measurements, the integration matches future readings against that user's
recent history.

## Notes

The scale only needs BLE advertisements, so ESPHome Bluetooth proxies work with
`connectable: false`.
