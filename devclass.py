from netmiko import ConnectHandler



#######################################################################################
# ------------------------------ classes part ----------------------------------------#
#######################################################################################


class CellSiteGateway:

    def __init__(self, ip, host):
        self.hostname = host
        self.ip_address = ip
        self.ssh_conn = None

        self.connection_status = True       # failed connection status, False if connection fails
        self.connection_error_msg = ""      # connection error message

        self.show_arp_log = ""
        self.show_arp_lora_log = ""
        self.show_isis_log = ""
        self.pagg = ""
        self.device_bs_info_list = []       # list of {port: , vlan: , ip: , mac: }
        self.port_bs = {}                   # {port1: [bs1, bs2]}
        self.commands = []
        self.show_description_log = {}      # {port: description}
        self.configuration_log = []
        self.show_errors = {"show_arp": 0,
                            "show_isis": 0,
                            "show_mac": 0,
                            "show_arp_lora": 0,
                            "make_config": 0}

    def connect(self, myusername, mypassword):
        self.ssh_conn = ConnectHandler(device_type="cisco_ios",
                                       ip=self.ip_address,
                                       username=myusername,
                                       password=mypassword)

    def disconnect(self):
        self.ssh_conn.disconnect()

    def show_arp(self):
        self.show_arp_log = self.ssh_conn.send_command(r"show ip arp vrf MA | exclude -|Incomplete")

    def show_arp_lora(self):
        self.show_arp_lora_log = self.ssh_conn.send_command(r"show ip arp vrf SMART_METERING | exclude -|Incomplete")

    def show_isis(self):
        self.show_isis_log = self.ssh_conn.send_command(r"show isis hostname | include pagg")

    def show_mac(self, mac, vlan):
        return self.ssh_conn.send_command(r"show mac-address-table address {} vlan {} | include DYNAMIC".format(mac,
                                                                                                                vlan))

    def show_description(self, port):
        return self.ssh_conn.send_command(r"show interfaces {} description".format(port))

    def configure(self, cmd_list):
        self.configuration_log.append(self.ssh_conn.send_config_set(cmd_list))

    def commit(self):
        self.configuration_log.append(self.ssh_conn.send_command('write memory'))

    def reset(self):
        self.connection_status = True       # failed connection status, False if connection fails
        self.connection_error_msg = ""      # connection error message

        self.show_arp_log = ""
        self.show_arp_lora_log = ""
        self.show_isis_log = ""
        self.pagg = ""
        self.device_bs_info_list = []       # list of {port: , vlan: , ip: , mac: }
        self.port_bs = {}                   # {port1: [bs1, bs2]}
        self.commands = []
        self.show_description_log = {}      # {port: description}
        self.configuration_log = []

