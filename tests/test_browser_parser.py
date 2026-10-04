"""Contract checks for the browser API decoder and displayed account units."""

import json
from pathlib import Path
import sys
import unittest

from Crypto.Cipher import AES

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "china_mobile_browser"))
from mobile_parser import (  # noqa: E402
    IV, KEY, balance_for_display, balance_from_page_text, decode_response,
    extract_sensors,
)


class BrowserParserTests(unittest.TestCase):
    def test_visible_balance_label(self):
        self.assertEqual(balance_from_page_text("话费余额\n116.63 元"), 116.63)
        self.assertEqual(balance_from_page_text("话费余额（元）\n116.63"), 116.63)
        self.assertEqual(balance_from_page_text("116.63元 话费余额"), 116.63)
        self.assertIsNone(balance_from_page_text("实时费用 126.63 元"))
        self.assertEqual(balance_for_display(126.63, "话费余额 116.63 元"), 116.63)
        self.assertEqual(balance_for_display(126.63, "实时费用 116.63 元"), 126.63)

    def test_encrypted_account_response(self):
        payload = {"data": {"realFeeQryRsp": {"curFeeTotal": "116.63"}}}
        raw = json.dumps(payload).encode()
        padding = 16 - len(raw) % 16
        encrypted = AES.new(KEY, AES.MODE_CBC, IV).encrypt(raw + bytes([padding]) * padding)
        self.assertEqual(decode_response(encrypted.hex()), payload)
        self.assertIsNone(decode_response("00" * 32))

    def test_allowance_units_and_missing_fields(self):
        responses = {
            "fareBalance": {"data": {"realFeeQryRsp": {"curFeeTotal": "116.63"}}},
            "getNewMarginInfo": {
                "data": {
                    "resultData": {
                        "planRemianFlowInfo": {
                            "planRemian": {
                                "remainNum": "99.36", "usedNum": "0.64",
                                "sumNum": "100", "unit": "04"
                            },
                            "directionalFlowInfo": {
                                "remainNum": "29.17", "usedNum": "0.82946",
                                "sumNum": "30", "unit": "04"
                            },
                        },
                        "planRemianVoiceInfo": {
                            "totalInfo": {"remainNum": "200", "sumNum": "200", "unit": "01"}
                        },
                    }
                }
            },
        }
        sensors = extract_sensors(responses)
        self.assertEqual(sensors["balance"], 116.63)
        self.assertEqual(sensors["general_remaining"], 99.36)
        self.assertEqual(sensors["directional_used"], 849.37)
        self.assertEqual(sensors["directional_remaining"], 29.17)
        self.assertEqual(sensors["voice_remaining"], 200)
        self.assertNotIn("voice_used", sensors)


if __name__ == "__main__":
    unittest.main()
