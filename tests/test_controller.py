import unittest
import sys
from unittest.mock import patch, MagicMock


class ControllerRechargeTest(unittest.TestCase):
    @patch('controller.RechargeV2')
    @patch('controller.notification.Notification')
    @patch('controller.load_dotenv')
    @patch.dict('os.environ', {
        'USERNAME': 'test_user',
        'PASSWORD': 'test_pass',
        'AMOUNT': '10000',
        'SLACK_WEBHOOK_URL': ''
    })
    def test_recharge_v2_exits_on_error(self, mock_load_dotenv, mock_notification, mock_recharge_v2):
        mock_recharge_instance = MagicMock()
        mock_recharge_instance.recharge.return_value = {
            "status": "error",
            "error": "keypad clicking failed"
        }
        mock_recharge_v2.return_value = mock_recharge_instance

        from controller import recharge_v2

        with self.assertRaises(SystemExit) as cm:
            recharge_v2()
        
        self.assertEqual(cm.exception.code, 1)

    @patch('controller.RechargeV2')
    @patch('controller.notification.Notification')
    @patch('controller.load_dotenv')
    @patch.dict('os.environ', {
        'USERNAME': 'test_user',
        'PASSWORD': 'test_pass',
        'AMOUNT': '10000',
        'SLACK_WEBHOOK_URL': ''
    })
    def test_recharge_v2_succeeds_without_exit(self, mock_load_dotenv, mock_notification, mock_recharge_v2):
        mock_recharge_instance = MagicMock()
        mock_recharge_instance.recharge.return_value = {
            "status": "success",
            "amount": 10000
        }
        mock_recharge_v2.return_value = mock_recharge_instance

        from controller import recharge_v2

        try:
            recharge_v2()
        except SystemExit:
            self.fail("recharge_v2() should not exit on success")


if __name__ == "__main__":
    unittest.main()
