import unittest
from unittest import TestCase
import json
import urwid

from microproxy.viewer.tui.widgets.message import Message
from microproxy.viewer.tui.widgets.detail_view import Detail


_message = \
    {
        "request": {
            "headers": {
                "Host": "github.com"
            },
            "path": "/index",
            "method": "GET",
            "version": "HTTP/1.1"
        },
        "response": {
            "headers": {
            },
            "code": 200,
            "version": "HTTP/1.1",
            "reason": "success"
        }
    }


def _create_message_content():
    return json.dumps(_message)


class MessageTest(TestCase):
    def test_create_message(self):
        message = Message([_create_message_content()], None)
        attr_map = message._w
        text = attr_map._original_widget

        self.assertEqual({None: "message focus"},
                         attr_map._focus_map)
        self.assertEqual({None: "message"},
                         attr_map._attr_map)
        self.assertEqual("200 GET   github.com/index",
                         text.text)


class DetailTest(TestCase):
    def _is_prop(self, expected_content, actual_prop):
        self.assertEqual(expected_content,
                         actual_prop._w._original_widget.text)

    def test_create_detail(self):
        message = Detail(_message)
        list_box = message._w
        list_walker = list_box.body

        self.assertTrue(isinstance(list_box, urwid.ListBox))
        self._is_prop("method: GET", list_walker[1])
        self._is_prop("path: /index", list_walker[2])
        self._is_prop("version: HTTP/1.1", list_walker[3])
        self._is_prop("Host: github.com", list_walker[5])
        self._is_prop("code: 200", list_walker[8])
        self._is_prop("reason: success", list_walker[9])
        self._is_prop("version: HTTP/1.1", list_walker[10])


if __name__ == "__main__":
    unittest.main()
