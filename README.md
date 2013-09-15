samba-vampire-drivers
=====================

Scripts for transfer of Windows print drivers to Samba servers.

Windows print system uses share `[PRINT$]` to store a provide native print drivers for Windows clients. This scripts allows to download the native Windows drivers from Windows machine (the `vampire-get.py`) and to upload and register the scripts to Samba machine (the `vampire-put.py`).


Usage:
-----

0. configure `vampire.ini` with credentials needed to download drivers
   from source server.
0. run `vampire-get.py`. All shared drivers will be downloaded from source server and    stored as .zip archive
0. (Optionally) modify the `metadata.json` file in the .zip archive.
0. run `vampire-put.py`. The script will upload all the drivers from .zip files to the destination server and register them as print driver.
0. run [`rpcclient`][rpcclient] with `setdriver` command manually to connect printer with appropriate driver.

Requisities
-----------
- working rpcclient

[Samba]: https://wiki.samba.org/index.php/Samba_as_a_print_server#Uploading_printer_drivers_for_Point.27n.27Print_driver_installation
[rpcclient]: http://www.samba.org/samba/docs/man/Samba-HOWTO-Collection/classicalprinting.html                       


