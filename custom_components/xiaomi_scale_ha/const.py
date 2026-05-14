DOMAIN = "xiaomi_scale_ha"

CONF_MAC = "mac"
CONF_USERS = "users"

DEFAULT_USERS_JSON = """[
  {
    "NAME": "User1",
    "GT": 50,
    "LT": 80,
    "SEX": "male",
    "HEIGHT": 175,
    "DOB": "1985-01-01"
  }
]"""

SIGNAL_MEASUREMENT = f"{DOMAIN}_measurement"
