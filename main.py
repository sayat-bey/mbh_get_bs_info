import queue
import os
from sys import argv
from threading import Thread
from deffile import *
from datetime import datetime

starttime = datetime.now()
current_date = starttime.strftime("%Y.%m.%d")
current_time = starttime.strftime("%H.%M.%S")
current_dir = os.getcwd()
folder = "{}\\logs\\{}\\".format(current_dir, current_date)     # current dir / logs / date /\=

if not os.path.exists(folder):
    os.mkdir(folder)

q = queue.Queue()

#######################################################################################
# ------------------------------ main part -------------------------------------------#
#######################################################################################


argv_dict = get_argv(argv)
username, password = get_user_pw()
devices = get_devinfo("devices.yaml")
bs_dict = load_excel('D:/MBH-local/CSG BS/actual IP_LTE_for_MBHv5.xlsx', "altel_bs.yaml", "lora_bs.yaml", folder)

total_devices = len(devices)

print("-------------------------------------------------------------------------------------------------------")
print("ip address       hostname                 comment")
print("---------------  -----------------------  -------------------------------------------------------------")


for i in range(argv_dict["maxth"]):

    th = Thread(target=mconnect, args=(username, password, q, bs_dict, argv_dict))
    th.setDaemon(True)
    th.start()


for device in devices:
    q.put(device)

q.join()

print("")

failed_connection_count = write_logs(devices, current_date, current_time, folder,
                                     export_device_info, export_excel, argv_dict)
duration = datetime.now() - starttime


#######################################################################################
# ------------------------------ last part -------------------------------------------#
#######################################################################################


print("--------------------------------------------------------------")
print("failed connection: {0}  total device number: {1}".format(failed_connection_count, total_devices))
print("elapsed time: {}".format(duration))
print("--------------------------------------------------------------\n")
