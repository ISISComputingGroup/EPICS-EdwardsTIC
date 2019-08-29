import unittest

from utils.channel_access import ChannelAccess
from utils.ioc_launcher import get_default_ioc_dir
from utils.test_modes import TestModes
from utils.testing import get_running_lewis_and_ioc

from parameterized import parameterized

DEVICE_PREFIX = "EDTIC_01"


IOCS = [
    {
        "name": DEVICE_PREFIX,
        "directory": get_default_ioc_dir("EDTIC"),
        "macros": {},
        "emulator": "edwardstic",
    },
]

# No recsim as this device makes heavy use of record redirection
TEST_MODES = [TestModes.DEVSIM, ]


PRI_SEVERITIES = {"OK": ChannelAccess.Alarms.NONE,
                  "Warning": ChannelAccess.Alarms.MINOR,
                  "Alarm": ChannelAccess.Alarms.MAJOR,
                  }


class EdwardsTICTests(unittest.TestCase):
    """
    Tests for the Edwards Turbo Instrument Controller (TIC) IOC.
    """

    def setUp(self):
        self._lewis, self._ioc = get_running_lewis_and_ioc("edwardstic", DEVICE_PREFIX)

        self.ca = ChannelAccess(device_prefix=DEVICE_PREFIX)
        self._lewis.backdoor_set_on_device("is_connected", True)

        self.ca.assert_setting_setpoint_sets_readback("No", "TURBO:STBY", set_point_pv="TURBO:SETSTBY", timeout=30)

    def test_GIVEN_turbo_pump_switched_on_WHEN_status_requested_THEN_status_reads_switched_on(self):
        # GIVEN
        self.ca.set_pv_value("TURBO:START", "On", wait=True)

        # THEN
        self.ca.assert_that_pv_is("TURBO:STA", "Running")

    def test_GIVEN_standby_mode_switched_on_WHEN_status_requested_THEN_standby_reads_switched_on(self):
        # GIVEN
        self.ca.set_pv_value("TURBO:SETSTBY", "Yes", wait=True)

        # THEN
        self.ca.assert_that_pv_is("TURBO:STBY", "Yes")

    def test_GIVEN_standby_mode_switched_off_WHEN_status_requested_THEN_standby_reads_switched_off(self):
        # GIVEN
        self.ca.set_pv_value("TURBO:SETSTBY", "No", wait=True)

        # THEN
        self.ca.assert_that_pv_is("TURBO:STBY", "No")

    @parameterized.expand([
        ("stopped", "Stopped", ChannelAccess.Alarms.NONE),
        ("starting_delay", "Starting Delay", ChannelAccess.Alarms.NONE),
        ("accelerating", "Accelerating", ChannelAccess.Alarms.NONE),
        ("running", "Running", ChannelAccess.Alarms.NONE),
        ("stopping_short_delay", "Stopping Short Delay", ChannelAccess.Alarms.NONE),
        ("stopping_normal_delay", "Stopping Normal Delay", ChannelAccess.Alarms.NONE),
        ("fault_braking", "Fault Breaking", ChannelAccess.Alarms.MAJOR),
        ("braking", "Braking", ChannelAccess.Alarms.NONE),
    ])
    def test_GIVEN_turbo_status_WHEN_turbo_status_read_THEN_turbo_status_read_back(self, turbo_status, IOC_status_label, expected_alarm):
        # GIVEN
        self._lewis.backdoor_run_function_on_device("set_turbo_pump_state", arguments=(turbo_status, ))

        # WHEN
        self.ca.assert_that_pv_is("TURBO:STA", IOC_status_label)
        self.ca.assert_that_pv_alarm_is("TURBO:STA", expected_alarm)


    @parameterized.expand([
        [key, value] for key, value in PRI_SEVERITIES.items()
    ])
    def test_GIVEN_turbo_status_with_priority_WHEN_turbo_status_read_THEN_turbo_status_priority_is_read_back(self, priority_state, expected_alarm):
        # GIVEN
        self._lewis.backdoor_run_function_on_device("set_turbo_priority", arguments=(priority_state, ))

        # THEN
        self.ca.assert_that_pv_is("TURBO:STA:PRI", priority_state)
        self.ca.assert_that_pv_alarm_is("TURBO:STA:PRI", expected_alarm)

    @parameterized.expand([
        (0, ChannelAccess.Alarms.NONE),
        (1, ChannelAccess.Alarms.MINOR),
        (-1, ChannelAccess.Alarms.MAJOR),
        (48, ChannelAccess.Alarms.MAJOR)
    ])
    def test_GIVEN_turbo_status_with_alert_WHEN_turbo_status_read_THEN_turbo_status_alert_is_read_back(self, alert_state, expected_alarm):
        # GIVEN
        self._lewis.backdoor_run_function_on_device("set_turbo_alert", arguments=(alert_state,))

        # THEN
        self.ca.assert_that_pv_is("TURBO:STA:ALERT", alert_state)
        self.ca.assert_that_pv_alarm_is("TURBO:STA:ALERT", expected_alarm)


    @parameterized.expand([
        ("turbo_status", "TURBO:STA"),
        ("turbo_speed", "TURBO:SPEED"),
        ("turbo_power", "TURBO:POWER"),
        ("turbo_norm", "TURBO:NORM"),
        ("turbo_standby", "TURBO:STBY"),
        ("turbo_cycle", "TURBO:CYCLE")
    ])
    def test_GIVEN_disconnected_device_WHEN_pump_status_read_THEN_PVs_read_invalid(self, _, base_pv):
        # GIVEN
        self._lewis.backdoor_set_on_device("is_connected", False)

        # WHEN
        self.ca.assert_that_pv_alarm_is(base_pv, self.ca.Alarms.INVALID, timeout=20)
        self.ca.assert_that_pv_alarm_is("{base}:ALERT".format(base=base_pv), self.ca.Alarms.INVALID)
        self.ca.assert_that_pv_alarm_is("{base}:PRI".format(base=base_pv), self.ca.Alarms.INVALID)
