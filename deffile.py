import yaml
import re
import time
from devclass import CellSiteGateway
from openpyxl import load_workbook, Workbook
from pprint import pformat
from netmiko.ssh_exception import NetMikoTimeoutException
# from getpass import getpass


#######################################################################################
# ------------------------------ def function part -----------------------------------#
#######################################################################################


def get_argv(argv):

    argv_dict = {"maxth": 20, "conf": False}
    mt_pattern = re.compile(r"mt([0-9]+)")

    for i in argv:
        if "mt" in i:
            match = re.search(mt_pattern, i)
            if match and int(match.group(1)) <= 100:
                argv_dict["maxth"] = int(match.group(1))
        elif i == "cfg":
            argv_dict["conf"] = True

    print("")
    print("max threads: {}  configuration mode: {}".format(argv_dict["maxth"], argv_dict["conf"]))

    return argv_dict


def get_user_pw():

    username = input("Enter login: ")
    password = getpass()

    return username, password


def get_devinfo(yaml_file):

    devices = []
    file = open(yaml_file, "r")
    devices_info = yaml.load(file)

    if isinstance(devices_info, dict):
        print("hostname : ip")
        for hostname, ip_address in devices_info.items():
            device = CellSiteGateway(ip=ip_address, host=hostname)
            devices.append(device)
    elif isinstance(devices_info, list) and "-" in devices_info[0]:    # hostname list
        print("hostname list")
        for hostname in devices_info:
            device = CellSiteGateway(ip=hostname, host=hostname)
            devices.append(device)
    elif isinstance(devices_info, list) and "-" not in devices_info[0]:  # ip list
        print("ip list")
        for ip_address in devices_info:
            device = CellSiteGateway(ip=ip_address, host="hostname")
            devices.append(device)

    file.close()
    print("")
    return devices


def mconnect(username, password, q, bs_dict, argv_dict):

    while True:
        device = q.get()
        i = 0
        while True:
            try:
                # print("{1:17}{2:25}{0:22}queue len: {3}".format("", device.ip_address, device.hostname))
                device.connect(username, password)
                show_commands(device)
                arp_log_parse(device)
                mac_log_parse(device)
                define_pagg(device)
                define_bs(device, bs_dict)
                port_bs(device)
                make_config(device)

                configure(device, argv_dict)
                device.disconnect()
                q.task_done()
                break

            except NetMikoTimeoutException as err_msg:
                device.connection_status = False
                device.connection_error_msg = str(err_msg)
                print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "timeout"))
                q.task_done()
                break

            except Exception as err_msg:
                if i == 5:
                    device.connection_status = False
                    device.connection_error_msg = str(err_msg)
                    print("{0:17}{1:25}{2:20} i={3}".format(device.ip_address, device.hostname,
                                                            "BREAK connection failed", i))
                    q.task_done()
                    break
                else:
                    i += 1
                    device.reset()
                    print("{0:17}{1:25}{2:20} i={3} msg={4}".format(device.ip_address, device.hostname,
                                                                    "ERROR connection failed", i, err_msg))
                    time.sleep(5)


def write_logs(devices, current_date, current_time, folder, exp_devinfo, exp_excel, argv_dict):

    failed_connection_count = 0
    exp_excel(devices, current_time, folder)

    conn_msg_filename = "{}{}_connection_error_msg.txt".format(folder, current_time)
    conn_msg_filename_file = open(conn_msg_filename, "w")

    device_info_filename = "{}{}_device_info.txt".format(folder, current_time)
    device_info_filename_file = open(device_info_filename, "w")

    config_filename = "{}{}_configuration_log.txt".format(folder, current_time)
    config_filename_file = open(config_filename, "w")

    for device in devices:
        exp_devinfo(device, device_info_filename_file)   # export device info: show, status, etc

        if argv_dict["conf"]:
            config_filename_file.write("#" * 80 + "\n")
            config_filename_file.write("### {} : {} ###\n\n".format(device.hostname, device.ip_address))
            config_filename_file.write("".join(device.configuration_log))
            config_filename_file.write("\n\n")

        if not device.connection_status:
            failed_connection_count += 1

            conn_msg_filename_file.write("{} {}\n\n".format(current_date, current_time))
            conn_msg_filename_file.write("-"*80 + "\n")
            conn_msg_filename_file.write("{} : {}\n\n".format(device.hostname, device.ip_address))
            conn_msg_filename_file.write("{}\n".format(device.connection_error_msg))

    conn_msg_filename_file.close()
    device_info_filename_file.close()
    config_filename_file.close()

    return failed_connection_count


#######################################################################################
# ------------------------------ get bs port -----------------------------------------#
#######################################################################################


def arp_log_parse(device):

    ip_mac_vlan_pattern = re.compile(r"Internet\s\s([0-9.]+)\s+[0-9]+\s{3}([0-9a-z.]+)\s\sARPA\s{3}Vlan([0-9]+)")

    exclude_mac = []
    exclude_ip_vlan = []    # 10.12.244.10 vlan 3010 -> 249103011
    exclude_vlan = [str(i) for i in range(1080, 1090)]
    exclude_vlan.extend([str(i) for i in range(4000, 4017)])
    exclude_vlan.append("4020")

    for line in device.show_arp_log.splitlines():
        ip_mac_vlan_match = re.search(ip_mac_vlan_pattern, line)

        if ip_mac_vlan_match:
            if ip_mac_vlan_match.group(2) in exclude_mac:
                continue
            elif ip_mac_vlan_match.group(3) in exclude_vlan:
                continue
            else:
                octets = ip_mac_vlan_match.group(1).split(".")
                third_octet = octets[2]
                fourth_octet = octets[3]
                vlan = ip_mac_vlan_match.group(3)
                ip_vlan = "{}{}{}".format(third_octet, fourth_octet, vlan)

                if ip_vlan in exclude_ip_vlan:
                    exclude_mac.append(ip_mac_vlan_match.group(2))
                    continue

                else:
                    device.device_bs_info_list.append({"ip": ip_mac_vlan_match.group(1),
                                                       "mac": ip_mac_vlan_match.group(2),
                                                       "vlan": ip_mac_vlan_match.group(3)})

                    exclude_mac.append(ip_mac_vlan_match.group(2))
                    exclude_ip_vlan.append("{}{}{}".format(str(int(third_octet)+5), fourth_octet, str(int(vlan)+1)))

    for line in device.show_arp_lora_log.splitlines():
        ip_mac_vlan_match = re.search(ip_mac_vlan_pattern, line)
        if ip_mac_vlan_match:
            device.device_bs_info_list.append({"ip": ip_mac_vlan_match.group(1),
                                               "mac": ip_mac_vlan_match.group(2),
                                               "vlan": ip_mac_vlan_match.group(3)})


def mac_log_parse(device):
    port_pattern = re.compile(r"[0-9]{3,4}\s{4}.{14}\s{4}DYNAMIC\s{5}(.+)")
    for i in device.device_bs_info_list:
        while True:
            try:
                show_mac_log = device.show_mac(i["mac"], i["vlan"])
                if len(show_mac_log) == 0:
                    device.show_errors["show_mac"] += 1
                    print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "ERROR show_mac"))
                else:
                    break
            except Exception as err_msg:
                print("{0:17}{1:25}{2:20} msg={3}".format(device.ip_address, device.hostname,
                                                          "EXCEPT ERROR show_mac", err_msg))
                device.show_errors["show_mac"] += 1
        for line in show_mac_log.splitlines():
            port_match = re.search(port_pattern, line)
            if port_match:
                i["port"] = port_match.group(1)


def define_pagg(device):
    pagg_pattern = re.compile(r"[0-9.]{14}\s([a-z]{4}-[0-9]{6}-pagg-[123])")
    for i in device.show_isis_log.splitlines():
        pagg_match = re.search(pagg_pattern, i)
        if pagg_match:
            device.pagg = pagg_match.group(1)


def show_commands(device):

    while True:
        try:
            device.show_arp()
            if len(device.show_arp_log) == 0:
                device.show_errors["show_arp"] += 1
                print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "ERROR show_arp"))
            else:
                break
        except Exception as err_msg:
            print("{0:17}{1:25}{2:20} msg={3}".format(device.ip_address, device.hostname,
                                                      "EXCEPT ERROR show_arp", err_msg))
            device.show_errors["show_arp"] += 1

    while True:
        try:
            device.show_isis()
            if len(device.show_isis_log) == 0:
                device.show_errors["show_isis"] += 1
                print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "ERROR show_isis"))
            else:
                break
        except Exception as err_msg:
            print("{0:17}{1:25}{2:20} msg={3}".format(device.ip_address, device.hostname,
                                                      "EXCEPT ERROR show_isis", err_msg))
            device.show_errors["show_isis"] += 1

    while True:
        try:
            device.show_arp_lora()
            if len(device.show_arp_lora_log) == 0:
                device.show_errors["show_arp_lora"] += 1
                print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "ERROR show_arp_lora"))
            else:
                break
        except Exception as err_msg:
            print("{0:17}{1:25}{2:20} msg={3}".format(device.ip_address, device.hostname,
                                                      "EXCEPT ERROR show_arp_lora", err_msg))
            device.show_errors["show_arp_lora"] += 1


def load_excel(excel_file, yaml_file, yaml_file2, folder):

    print("load_excel: excel is loading")
    wb = load_workbook(excel_file)
    print("load_excel: excel is loaded")
    sheet_names = ['AK', 'AL', 'AT', 'AU', 'AS', 'KO', 'SH', 'KZ', 'KS', 'TA', 'KA', 'PE', 'UR', 'PA', 'UK', 'SE']
    sheets = [wb[i] for i in sheet_names]
    result = {}     # bs abis ip : bs

    for sheet in sheets:
        i = 3

        while True:
            bs_ip = sheet.cell(row=i, column=5).value
            bs = sheet.cell(row=i, column=1).value

            if bs_ip:
                i += 1
                if bs:
                    result[bs_ip] = bs
            else:
                break

    with open(yaml_file, "r") as file:

        altel_bs = yaml.load(file)
        result.update(altel_bs)
        print("load_excel: altel bs is added")

    with open(yaml_file2, "r") as file2:

        lora_bs = yaml.load(file2)
        result.update(lora_bs)
        print("load_excel: lora bs is added")

    with open(folder + "bs_ip.yaml", "w") as output_file:

        yaml.dump(result, output_file, default_flow_style=False)
        print("load_excel: bs_ip is exported")

    return result


def export_excel(devices, current_time, folder):

    filename = "{}{}_excel_bs.xlsx".format(folder, current_time)
    wb = Workbook()
    sheet = wb.active
    sheet.append(["pagg", "csg hostname", "csg loopback0", "csg port", "bs", "comments"])
    for device in devices:
        if device.connection_status:
            for bs in device.device_bs_info_list:
                sheet.append([device.pagg, device.hostname, device.ip_address, bs["port"], bs["bs"]])
            if len(device.device_bs_info_list) == 0:
                sheet.append([device.pagg, device.hostname, device.ip_address, "-", "-", "no bs"])
        else:
            sheet.append(["-", device.hostname, device.ip_address, "-", "-", "unavailable"])

    wb.save(filename)


def define_bs(device, bs_dict):

    for bs in device.device_bs_info_list:
        bs_ip = bs["ip"]

        if bs_dict.get(bs_ip):
            bs["bs"] = bs_dict[bs_ip]
        else:
            bs["bs"] = bs_ip


def port_bs(device):

    port_bs_dict = {}   # {port: [bs list]}

    for bs in device.device_bs_info_list:
        bsport = bs["port"]
        bsname = bs["bs"]

        if port_bs_dict.get(bsport):
            port_bs_dict[bsport].append(bsname)
        else:
            port_bs_dict[bsport] = [bsname]

    for port, bs_list in port_bs_dict.items():
        device.port_bs[port] = []

        for bs in bs_list:
            if "lora" in bs:
                device.port_bs[port].insert(0, bs)
            else:
                device.port_bs[port].append(bs)


def export_device_info(device, export_file):

    export_file.write("#" * 80 + "\n")
    export_file.write("### {} : {} ###\n\n".format(device.hostname, device.ip_address))

    export_file.write("-" * 80 + "\n")
    export_file.write("device.show_arp_log\n\n")
    export_file.write(device.show_arp_log)
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.show_isis_log\n\n")
    export_file.write(device.show_isis_log)
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.device_bs_info_list\n\n")
    export_file.write(pformat(device.device_bs_info_list))
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.commands\n\n")
    export_file.write(pformat(device.commands))
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.port_bs\n\n")
    export_file.write(pformat(device.port_bs))
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.show_errors\n\n")
    export_file.write(pformat(device.show_errors))
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.connection_status (True is OK)\n\n")
    export_file.write(str(device.connection_status))
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.connection_error_msg (Empty if OK)\n\n")
    export_file.write(device.connection_error_msg)
    export_file.write("\n\n")

    export_file.write("-" * 80 + "\n")
    export_file.write("device.show_description_log\n\n")
    export_file.write(pformat(device.show_description_log))
    export_file.write("\n\n")


def make_config(device):

    description_pattern = re.compile(r".*up\s+up\s+(.*) BS: (.*)")
    description_old_pattern = re.compile(r".*up\s+up\s+(.*)")

    for port, bs_list in device.port_bs.items():
        while True:
            try:
                description = device.show_description(port)
                if len(description) == 0:
                    device.show_errors["make_config"] += 1
                    print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "ERROR make_config"))
                else:
                    device.show_description_log[port] = description
                    break
            except Exception as err_msg:
                print("{0:17}{1:25}{2:20} msg={3}".format(device.ip_address, device.hostname,
                                                          "EXCEPT make_config", err_msg))
                device.show_errors["make_config"] += 1

        for line in description.splitlines():
            description_match = re.search(description_pattern, line)
            description_old_match = re.search(description_old_pattern, line)

            if description_match:
                extra_text = description_match.group(1)     # (extra_text) BS: bs_text
                bs_text = description_match.group(2)        # extra_text BS: (bs_text)

                bs_set = set(bs_text.split())
                if bs_set != set(device.port_bs[port]):
                    if len(extra_text) != 0:
                        device.commands.append("interface {}".format(port))
                        device.commands.append("description {} BS: {}".format(extra_text, " ".join(bs_list)))
                    else:
                        device.commands.append("interface {}".format(port))
                        device.commands.append("description BS: {}".format(" ".join(bs_list)))

            elif description_old_match:
                if "lora" in " ".join(bs_list) and len(bs_list) == 1:
                    if description_old_match.group(1) != "".join(bs_list):
                        device.commands.append("interface {}".format(port))
                        device.commands.append("description {}".format(" ".join(bs_list)))
                elif "lora" in " ".join(bs_list) and len(bs_list) > 1:
                    device.commands.append("interface {}".format(port))
                    device.commands.append("description BS: {}".format(" ".join(bs_list)))
                else:
                    device.commands.append("interface {}".format(port))
                    device.commands.append("description BS: {}".format(" ".join(bs_list)))


def configure(device, argv_dict):

    if argv_dict["conf"]:
        if len(device.commands) != 0:
            device.configure(device.commands)
            device.commit()
        else:
            print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "cfg is not needed"))

    else:
        if len(device.commands) != 0:
            print("{0:17}{1:25}{2:20}".format(device.ip_address, device.hostname, "cfg is needed"))
