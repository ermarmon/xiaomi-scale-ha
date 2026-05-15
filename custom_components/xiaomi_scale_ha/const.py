DOMAIN = "xiaomi_scale_ha"

CONF_MAC = "mac"
CONF_USERS = "users"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_PERSISTENT_NOTIFICATION = "persistent_notification"
CONF_NOTIFY_ASSIGNED = "notify_assigned"
CONF_IMPEDANCE_WAIT_SECONDS = "impedance_wait_seconds"
CONF_USER_NOTIFY_SERVICE = "NOTIFY_SERVICE"
CONF_ALEXA_ACTIONS = "alexa_actions"
CONF_ALEXA_ACTION_SCRIPT = "alexa_action_script"
CONF_ALEXA_SUPPRESS_CONFIRMATION = "alexa_suppress_confirmation"
CONF_USER_ALEXA_DEVICE = "ALEXA_DEVICE"

DEFAULT_USERS_JSON = """[
  {
    "NAME": "User1",
    "GT": 50,
    "LT": 80,
    "SEX": "male",
    "HEIGHT": 175,
    "DOB": "1985-01-01",
    "NOTIFY_SERVICE": "",
    "ALEXA_DEVICE": ""
  }
]"""

SIGNAL_MEASUREMENT = f"{DOMAIN}_measurement"

EVENT_PENDING = f"{DOMAIN}_pending_measurement"
EVENT_ASSIGNED = f"{DOMAIN}_measurement_assigned"
EVENT_DISCARDED = f"{DOMAIN}_measurement_discarded"

SERVICE_ASSIGN_PENDING = "assign_pending"
SERVICE_DISCARD_PENDING = "discard_pending"
SERVICE_SEND_PENDING_NOTIFICATION = "send_pending_notification"
SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_DELETE_HISTORY_MEASUREMENT = "delete_history_measurement"
