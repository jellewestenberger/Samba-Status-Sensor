# Samba File Reservation Sensor



This script creates a MQTT sensor that lists all files currently being shared over Samba/Cifs. Additionally, it includes the attributes shown in the example below:

![](resources/smbcard.png)

# Installation:
It is assumed that `/usr/local/samba/bin/smbstatus` exists. Edit the corresponding line to match your location of the `smbstatus` binary.
Furthermore, this command is called with `ssh -i /home/pi/.ssh/id_rsa user@host "/usr/local/samba/bin/smbstatus"` which in this setting only works if you have already set up a ssh-key pair between your machines that does not require a passphrase. 
You can create a ssh-key pair with `ssh-keygen` and subsequently `ssh-copy-id`. Edit the `/home/pi/.ssh/id_rsa` part of the command to match your ssh identity location.

## Cron job
Since the script is configured to run only once for a single update it is advised to create a cron job for regular updates.

### Example: 
run `crontab -e` and add the following to the end of the file:
```
*\1 * * * *  python3 <path to smbstatus.py>
```
This job runs every minute and automatically installed after saving the crontab file.