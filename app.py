import logging
import sqlite3
from flask import Flask, request, jsonify
import textfsm
from netmiko import ConnectHandler

from db import get_db, execute_query, create_vlan_table, sync_vlan_with_db
from auth import authenticate

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, filename='vlan_sync.log', format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/sync', methods=['POST'])
def sync_vlans():
    """Sync VLANs from Cisco switches/routers"""
    # Check authentication
    token = request.headers.get('Authorization')
    if not authenticate(token):
        logging.warning("Authentication failed")
        return jsonify({'message': 'Authentication failed'}), 401

    cisco_data = request.get_json()
    if not cisco_data:
        logging.warning("No data provided")
        return jsonify({'message': 'No data provided'}), 400

    vlan_data = []
    # Extract VLAN data using textfsm parser
    with open('cisco_vlan_template.textfsm', 'r') as template_file:
        template = textfsm.TextFSM(template_file)
        try:
            result = template.ParseText(cisco_data)
            for vlan in result:
                vlan_data.append({
                    'vlan_id': int(vlan[0]),
                    'name': vlan[1],
                    'description': vlan[2]
                })
        except Exception as e:
            logging.error(f"TextFSM parsing error: {str(e)}")
            return jsonify({'error': 'TextFSM parsing error', 'message': str(e)}), 500

    # Create/Update/Delete VLANs in the database
    create_vlan_table()

    # Sync VLAN data with the database
    for vlan in vlan_data:
        existing_vlan = execute_query("SELECT * FROM vlans WHERE vlan_id=?", (vlan['vlan_id'],))
        if existing_vlan:
            # VLAN already exists, update the record
            query = '''UPDATE vlans SET name=?, description=? WHERE vlan_id=?;'''
            if execute_query(query, (vlan['name'], vlan['description'], vlan['vlan_id'])) is None:
                logging.error(f"Failed to update VLAN with ID {vlan['vlan_id']} in the database")
        else:
            # VLAN doesn't exist, insert a new record
            sync_vlan_with_db(vlan)

    # Delete VLANs that don't exist in the received data
    existing_vlans = execute_query("SELECT * FROM vlans")
    existing_vlan_ids = [vlan['vlan_id'] for vlan in vlan_data]
    for vlan in existing_vlans:
        if vlan['vlan_id'] not in existing_vlan_ids:
            query = '''DELETE FROM vlans WHERE vlan_id=?;'''
            if execute_query(query, (vlan['vlan_id'],)) is None:
                logging.error(f"Failed to delete VLAN with ID {vlan['vlan_id']} from the database")

    logging.info("VLAN sync completed successfully")
    return jsonify({'message': 'VLAN sync completed successfully'}), 200


@app.route('/sync/<device>', methods=['POST'])
def sync_vlan_with_device(device):
    """Sync VLANs with a specific device"""
    # Check authentication
    token = request.headers.get('Authorization')
    if not authenticate(token):
        return jsonify({'message': 'Authentication failed'}), 401

    # Fetch VLAN data from the database
    query = 'SELECT * FROM vlans'
    try:
        vlans = execute_query(query, fetch_all=True)
    except sqlite3.Error as e:
        return jsonify({'error': 'Database error', 'message': str(e)}), 500

    # Connect to the device using Netmiko
    device_info = {
        'device_type': 'cisco_ios',
        'ip': device,
        'username': 'your_username',
        'password': 'your_password',
        'secret': 'your_enable_password',
        'port': 22,
    }
    try:
        net_connect = ConnectHandler(**device_info)
        net_connect.enable()
    except Exception as e:
        return jsonify({'error': 'Failed to connect to device', 'message': str(e)}), 500

    # Update VLAN configuration on the device
    for vlan in vlans:
        vlan_id = vlan['vlan_id']
        vlan_name = vlan['name']
        vlan_description = vlan['description']
        command = f'vlan {vlan_id}\nname {vlan_name}\ndescription {vlan_description}'
        try:
            output = net_connect.send_config_set([command])
            logging.info(f"Updated VLAN {vlan_id} on device {device}: {output}")
        except Exception as e:
            logging.error(f"Failed to update VLAN {vlan_id} on device {device}: {str(e)}")

    # Close the Netmiko connection
    net_connect.disconnect()

    logging.info(f"VLAN sync with device {device} completed successfully")
    return jsonify({'message': f'VLAN sync with device {device} completed successfully'}), 200



if __name__ == '__main__':
    app.run(debug=True)