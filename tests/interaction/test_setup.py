import io
from pathlib import Path
import queue
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'windows-bridge'))
from phonexr_bridge.setup_ui import addresses, bridge_command, private_ipv4
from phonexr_bridge.__main__ import read_controls


class SetupTests(unittest.TestCase):
    def test_address_boundary(self):
        for address in ('10.0.0.1', '172.16.0.1', '172.31.255.254', '192.168.1.5', '169.254.2.3'):
            self.assertTrue(private_ipv4(address))
        for address in ('127.0.0.1', '0.0.0.0', '8.8.8.8', '172.32.0.1', 'example.com', '::1', '192.168.1.2 --enable'):
            self.assertFalse(private_ipv4(address))
            with self.assertRaises(ValueError):
                bridge_command(address)

    def test_command_starts_disabled_and_uses_pipe_control(self):
        command = bridge_command('192.168.1.5')
        self.assertEqual(command[-3:], ['--host', '192.168.1.5', '--gui-control'])
        self.assertNotIn('--mouse-fallback', command)
        self.assertNotIn('e', command)

    def test_discovery_filters_public_and_duplicates(self):
        rows = [(None, None, None, None, (value, 0)) for value in
                ('192.168.2.3', '8.8.8.8', '127.0.0.1', '192.168.2.3')]
        with patch('socket.getaddrinfo', return_value=rows):
            self.assertEqual(addresses(), ['192.168.2.3'])

    def test_pipe_eof_requests_release_exit(self):
        commands = queue.SimpleQueue()
        read_controls(io.StringIO('E\nunknown\nd\n'), commands)
        self.assertEqual([commands.get_nowait() for _ in range(3)], ['e', 'd', 'q'])
        self.assertTrue(commands.empty())

    def test_pipe_read_failure_also_requests_exit(self):
        class Broken:
            def __iter__(self):
                raise OSError('pipe closed')
        commands = queue.SimpleQueue()
        with self.assertRaises(OSError):
            read_controls(Broken(), commands)
        self.assertEqual(commands.get_nowait(), 'q')
