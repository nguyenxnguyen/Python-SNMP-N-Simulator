import paramiko
import socket
import requests
import xml.etree.ElementTree as ET


class CAPM(object):
    @staticmethod
    def dnat_for_dc(user_name, password, server, table):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # server = 'certvn-dc5'
        # fake_ip = '123.0.0.2'
        # real_ip = '10.132.152.169'
        # real_port = '64002'
        ssh.connect(server, username=user_name, password=password)
        cmd_1 = 'echo "1" > /proc/sys/net/ipv4/ip_forward'
        ssh.exec_command(cmd_1)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("google.com.vn", 80))
        real_ip = (s.getsockname()[0])
        s.close()
        #real_ip = socket.gethostbyname(socket.getfqdn())
        for row in table:
            if not row:
                continue
            row = list(row)
            fake_ip = row[0]
            real_port = row[1]
            cmd_2 = 'iptables -t nat -A OUTPUT -d %s -p UDP --dport 161 -j DNAT --to-destination %s:%s' \
                    % (fake_ip, real_ip, real_port)
            cmd_3 = 'iptables -t nat -A OUTPUT -d %s -p TCP --dport 161 -j DNAT --to-destination %s:%s' \
                    % (fake_ip, real_ip, real_port)
            cmd_4 = 'iptables -t nat -A OUTPUT -d %s -p ICMP -j DNAT --to-destination %s' \
                    % (fake_ip, real_ip)
            ssh.exec_command(cmd_2)
            ssh.exec_command(cmd_3)
            ssh.exec_command(cmd_4)
        ssh.close()

    @staticmethod
    def check_state(da_host, table):
        url_devices = 'http://%s:8581/rest/devices/accessible/' % da_host
        r_get = requests.get(url_devices)
        tree = ET.ElementTree(ET.fromstring(r_get.content))
        response_root = tree.getroot()
        list_ip = []
        for node in response_root:
            device_id = node.find('ID').text
            device = node.find('Device')
            ip_address = device.find('PrimaryIPAddress').text
            list_ip.append(ip_address)
        for row in table:
            if not row:
                continue
            row = list(row)
            if row[0] in list_ip:
                row[6] = 'Discovered'
            yield row

    @staticmethod
    def rm_device(da_host, table):
        url_devices = 'http://%s:8581/rest/devices/accessible/' % da_host
        r_get = requests.get(url_devices)
        tree = ET.ElementTree(ET.fromstring(r_get.content))
        response_root = tree.getroot()
        list_id = {}
        list_ip = []
        for row in table:
            if not row:
                continue
            row = list(row)
            list_ip.append(row[0])
        for node in response_root:
            device_id = node.find('ID').text
            device = node.find('Device')
            ip_address = device.find('PrimaryIPAddress').text
            if ip_address in list_ip:
                list_id[ip_address] = device_id

        url_devices_delete = 'http://%s:8581/rest/devices/accessible/deletelist' % da_host
        headers = {'Content-Type': 'application/xml'}
        root = ET.Element('DeleteList')
        for i in list_id.keys():
            l1 = ET.SubElement(root, 'ID')
            l1.text = list_id[i]
        body = ET.tostring(root)
        r_post = requests.post(url_devices_delete, headers=headers, data=body)
        print r_post.status_code

    def discover(self, da_host, profile, table):
        url_profile = 'http://%s:8581/rest/discoveryprofiles/' % da_host
        r_get = requests.get(url_profile)
        tree = ET.ElementTree(ET.fromstring(r_get.content))
        response_root = tree.getroot()
        list_id = []
        for node in response_root:
            item = node.find('Item')
            item_name = item.find('Name').text
            id = node.find('ID').text
            if profile in item_name:
                list_id = []
                daDiscoveryProfileId = id
                break
            else:
                list_id.append(int(id))

        if list_id:
            next_id = max(list_id) + 1
            daDiscoveryProfileId = str(next_id)

            print daDiscoveryProfileId

        #daDiscoveryProfileId = '3970'
        #url_profile = 'http://%s:8581/rest/discoveryprofiles/' % da_host
        if 'daDiscoveryProfileId' in locals():
            url_profile_id = 'http://%s:8581/rest/discoveryprofiles/%s' % (da_host, daDiscoveryProfileId)
            headers = {'Content-Type': 'application/xml'}
            root = ET.Element('DiscoveryProfile')
            root.attrib['version'] = '1.0.0'
            l1_IPListList = ET.SubElement(root, 'IPListList')
            for row in table:
                if not row:
                    continue
                row = list(row)
                l2_IPList = ET.SubElement(l1_IPListList, 'IPList')
                l2_IPList.text = row[0]
            l1_RunStatus = ET.SubElement(root, 'RunStatus')
            l1_RunStatus.text = 'START'
            l1_Item = ET.SubElement(root, 'Item')
            l1_Item.attrib['version'] = '1.0.0'
            l2_Name = ET.SubElement(l1_Item, 'Name')
            l2_Name.text = profile
            body = ET.tostring(root)

            r_put = requests.put(url_profile_id, headers=headers, data=body)
            print r_put.status_code
            if r_put.status_code == 200:
                table_return = list(self.check_state(da_host, table))
            else:
                table_return = table
            return table_return
        else:
            return ""

#discover('certvn-da5', ['96.0.0.1'])