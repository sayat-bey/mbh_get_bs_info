# mbh_get_bs_info

create logs folder
create devices.csv file with list of devices inside:
- hostname1,ip1,ios
- hostname2,ip2,ios xe
- hostname3,ip3,ios xr


v3 (03.12.2019)
- анализ портов на PAGG
- сокращение description 
  AL7370 AL7371 -> AL7370_7371
- обновление description на interface vlan

v4 (09.03.2021)
- переписан код, оптимизирован

v4.4 (10.03.2021)
- способность сохранить конфигурацию на IOS после сообщения:
  Warning: Attempting to overwrite an NVRAM configuration previously written
  by a different version of the system image. \[confirm]?
  
v4.6 (11.03.2021)
- добавлен IOS XE

v4.8 (03.04.2021)
- добавлена поддержка BVI на IOS XR
- объединение одинаковых ячеек в Excel (pagg, csg, csg lo0)

v5 (07.07.2021)
- проверка на работу оптических БС по РРЛ