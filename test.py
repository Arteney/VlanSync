import unittest
import sqlite3
from unittest.mock import patch
from app import app, execute_query
from auth import AUTH_TOKEN

class TestVlanSync(unittest.TestCase):

    def setUp(self):
        app.testing = True
        self.app = app.test_client()
        self.db = sqlite3.connect('vlan.db')
        self.db.execute('CREATE TABLE IF NOT EXISTS vlans (id INTEGER PRIMARY KEY AUTOINCREMENT, vlan_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL)')

    def tearDown(self):
        self.db.execute('DROP TABLE vlans')
        self.db.close()

    def test_sync_vlans(self):
        # Test successful synchronization
        with patch('app.execute_query') as mock_execute_query:
            mock_execute_query.return_value = None
            payload = '[["1", "VLAN1", "VLAN1 Desc"], ["2", "VLAN2", "VLAN2 Desc"]]'
            response = self.app.post('/sync', headers={'Authorization': 'your_auth_token'}, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {'message': 'VLAN sync completed successfully'})
            mock_execute_query.assert_called()

        # Test authentication failure
        response = self.app.post('/sync', headers={'Authorization': 'invalid_token'}, json='[["1", "VLAN1", "VLAN1 Desc"]]')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {'message': 'Authentication failed'})

        # Test missing data
        response = self.app.post('/sync', headers={'Authorization': 'your_auth_token'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {'message': 'No data provided'})

        # Test textfsm parsing error
        with patch('app.textfsm.TextFSM.ParseText') as mock_parse_text:
            mock_parse_text.side_effect = Exception('Parsing error')
            payload = 'invalid data'
            response = self.app.post('/sync', headers={'Authorization': 'your_auth_token'}, json=payload)
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json, {'error': 'TextFSM parsing error', 'message': 'Parsing error'})
            mock_parse_text.assert_called()

        # Test database error
        with patch('app.get_db') as mock_get_db:
            mock_get_db.side_effect = sqlite3.Error('Database error')
            payload = '[["1", "VLAN1", "VLAN1 Desc"]]'
            response = self.app.post('/sync', headers={'Authorization': 'your_auth_token'}, json=payload)
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json, {'error': 'Database error', 'message': 'Database error'})
            mock_get_db.assert_called()

    def test_sync_vlan_with_device(self):
      with app.test_client() as client:
        # Add some VLANs to the database
        execute_query("INSERT INTO vlans (vlan_id, name, description) VALUES (?, ?, ?);", (10, 'VLAN10', 'Test VLAN 10'))
        execute_query("INSERT INTO vlans (vlan_id, name, description) VALUES (?, ?, ?);", (20, 'VLAN20', 'Test VLAN 20'))
        execute_query("INSERT INTO vlans (vlan_id, name, description) VALUES (?, ?, ?);", (30, 'VLAN30', 'Test VLAN 30'))

        # Sync VLANs with a non-existent device
        response = client.post('/sync/non-existent-device', headers={'Authorization': AUTH_TOKEN})
        assert response.status_code == 404

        # Sync VLANs with a device that doesn't exist in the database
        response = client.post('/sync/device2', headers={'Authorization': AUTH_TOKEN})
        assert response.status_code == 500

        # Sync VLANs with a device that has no credentials
        response = client.post('/sync/device1', headers={'Authorization': AUTH_TOKEN})
        assert response.status_code == 500

        # Sync VLANs with a device that has invalid credentials
        response = client.post('/sync/device1', json={'username': 'invalid_user', 'password': 'invalid_password'},
        headers={'Authorization': AUTH_TOKEN})
        assert response.status_code == 500

        # Sync VLANs with a device that has valid credentials
        response = client.post('/sync/device1', json={'username': 'user1', 'password': 'pass1'},
        headers={'Authorization': AUTH_TOKEN})
        assert response.status_code == 200

        # Check if VLANs are synced with the device
        vlans = execute_query("SELECT * FROM vlans", fetch_all=True)
        assert len(vlans) == 3

        # Clean up the database
        execute_query("DELETE FROM vlans")