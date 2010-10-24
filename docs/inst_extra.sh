#!/bin/bash -x

#
# This will install mail support, configure automated installation of security patches, and
# install all needed security patches
# 

#
# Install mail support
# 
echo "Installing mail support"
apt-get -y install mailutils
apt-get -y install sendmail-bin

# Configure Automatic Security Updates 
#
# See: https://help.ubuntu.com/community/AutomaticSecurityUpdates
#

echo "Configuring auto-update"
PDCONTENTS='APT::Periodic::Enable "1"; 
APT::Periodic::Update-Package-Lists "1"; 
APT::Periodic::Download-Upgradeable-Packages "1"; 
APT::Periodic::AutocleanInterval "5"; 
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::RandomSleep "1800"; 
'
/bin/echo "$PDCONTENTS"  > /etc/apt/apt.conf.d/10periodic

PDPATCH='*** /etc/apt/apt.conf.d/50unattended-upgrades.orig	2010-04-29 14:46:10.000000000 +0000
--- /tmp/50unattended-upgrades.orig	2010-10-24 17:53:48.000000000 +0000
***************
*** 16,22 ****
  // If empty or unset then no email is sent, make sure that you
  // have a working mail setup on your system. The package 'mailx'
  // must be installed or anything that provides /usr/bin/mail.
! //Unattended-Upgrade::Mail "root@localhost";
  
  // Do automatic removal of new unused dependencies after the upgrade
  // (equivalent to apt-get autoremove)
--- 16,22 ----
  // If empty or unset then no email is sent, make sure that you
  // have a working mail setup on your system. The package 'mailx'
  // must be installed or anything that provides /usr/bin/mail.
! Unattended-Upgrade::Mail "root@localhost";
  
  // Do automatic removal of new unused dependencies after the upgrade
  // (equivalent to apt-get autoremove)
***************
*** 24,32 ****
  
  // Automatically reboot *WITHOUT CONFIRMATION* if a 
  // the file /var/run/reboot-required is found after the upgrade 
! //Unattended-Upgrade::Automatic-Reboot "false";
  
  
  // Use apt bandwidth limit feature, this example limits the download
  // speed to 70kb/sec
! //Acquire::http::Dl-Limit "70";
\ No newline at end of file
--- 24,32 ----
  
  // Automatically reboot *WITHOUT CONFIRMATION* if a 
  // the file /var/run/reboot-required is found after the upgrade 
! Unattended-Upgrade::Automatic-Reboot "false";
  
  
  // Use apt bandwidth limit feature, this example limits the download
  // speed to 70kb/sec
! //Acquire::http::Dl-Limit "70";'
echo "$PDPATCH" | patch -bN /etc/apt/apt.conf.d/50unattended-upgrades

echo "Installing security patches -- this may reboot at end"
/etc/cron.daily/apt




