import unittest

from rechargeV2 import RechargeV2


class FakeSwitchTo:
    def __init__(self, driver):
        self._driver = driver

    def window(self, handle):
        self._driver.current_handle = handle


class FakeDriver:
    def __init__(self, urls_by_handle):
        self.window_handles = list(urls_by_handle)
        self.urls_by_handle = urls_by_handle
        self.current_handle = self.window_handles[0]
        self.switch_to = FakeSwitchTo(self)

    @property
    def current_url(self):
        return self.urls_by_handle[self.current_handle]


class RechargeV2PopupTest(unittest.TestCase):
    def test_switches_to_ecaccount_popup_window(self):
        driver = FakeDriver(
            {
                "main": "https://www.dhlottery.co.kr/mypage/mndpChrg",
                "popup": "https://www.dhlottery.co.kr/ecAccount.do",
            }
        )

        RechargeV2()._switch_to_ecaccount_popup(driver, timeout_seconds=0.1)

        self.assertEqual(driver.current_handle, "popup")


if __name__ == "__main__":
    unittest.main()
