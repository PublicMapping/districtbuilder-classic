#!/bin/bash -x

#
# This will
#  - install mail support
#  - configure automated installation of security patches, and
#  - install automatic cleanup of the reports directory
#  - install all needed security patches
# 

#
# Install mail support
# 
echo "Installing gdal"
apt-get -y install gdal-bin

#
# Install mail support
# 
echo "Installing mail support"
apt-get -y install mailutils
apt-get -y install sharutils
apt-get -y install sendmail-bin
apt-get -y install sensible-mda

SMPATCH='*** /etc/mail/sendmail.mc.good       2010-12-15 22:01:17.773507002 +0000
--- /etc/mail/sendmail.mc 2011-04-19 17:46:41.635571035 +0000
***************
*** 107,109 ****
--- 107,112 ----
  MASQUERADE_AS(`publicmapping.org'\'')dnl
  FEATURE(`allmasquerade'\'')dnl
  FEATURE(`masquerade_envelope'\'')dnl
+
+ # max file size DOS prevention
+ define(`confMAX_MESSAGE_SIZE'\'',`524288'\'')dnl
'

echo "$SMPATCH" | patch -bN /etc/mail/sendmail.mc

#
# Install report directory cleanup
# 
echo "Updating BARD"
echo 'install.packages("BARD",dependencies=TRUE,repos="http://cran.r-project.org")' | R --slave 

#
# Install report directory cleanup
# 
echo "Installing directory cleanup"
apt-get -y install tmpreaper
echo "5 0 * * *      /usr/sbin/tmpreaper 2d /projects/PublicMapping/local/reports/ /tmp/ > /dev/null 2>&1" > /tmp/wwwcron
crontab -u www-data /tmp/wwwcron


#
# Install usage reporting
#

echo "Installing cron job to send usage reports to publicmapping.org"
USAGEREP='#!/bin/sh

# send usage reports
(cut -d" " -f 1,4-7 /var/log/apache2/publicmapping-access.log | grep /district | cut -d . -f3-  | gzip -c | uuencode - | mail -s "logs from `hostname -f`" support@publicmapping.org) 1>/dev/null 2>/dev/null
'
echo "$USAGEREP"> /etc/cron.daily/publicmapping
chmod a+x,a+r /etc/cron.daily/publicmapping


# Configure Automatic Security Updates 
#
# See: https://help.ubuntu.com/community/AutomaticSecurityUpdates
#

echo "Configuring auto-update"

apt-get -y install unattended-upgrades
PDPATCH='
*** 50unattended-upgrades.orig  2010-08-26 16:48:50.000000000 +0000
--- 50unattended-upgrades.good  2011-04-19 18:10:42.345571039 +0000
***************
*** 18,24 ****
  // If empty or unset then no email is sent, make sure that you
  // have a working mail setup on your system. The package 'mailx'
  // must be installed or anything that provides /usr/bin/mail.
! //Unattended-Upgrade::Mail "root@localhost";
  
  // Do automatic removal of new unused dependencies after the upgrade
  // (equivalent to apt-get autoremove)
--- 18,24 ----
  // If empty or unset then no email is sent, make sure that you
  // have a working mail setup on your system. The package '\''mailx'\''
  // must be installed or anything that provides /usr/bin/mail.
! Unattended-Upgrade::Mail "root@localhost";
  
  // Do automatic removal of new unused dependencies after the upgrade
  // (equivalent to apt-get autoremove)
***************
*** 26,34 ****
  
  // Automatically reboot *WITHOUT CONFIRMATION* if a 
  // the file /var/run/reboot-required is found after the upgrade 
! //Unattended-Upgrade::Automatic-Reboot "false";
  
  
  // Use apt bandwidth limit feature, this example limits the download
  // speed to 70kb/sec
! //Acquire::http::Dl-Limit "70";
\ No newline at end of file
--- 26,34 ----
  
  // Automatically reboot *WITHOUT CONFIRMATION* if a 
  // the file /var/run/reboot-required is found after the upgrade 
! Unattended-Upgrade::Automatic-Reboot "true";
  
  
  // Use apt bandwidth limit feature, this example limits the download
  // speed to 70kb/sec
! //Acquire::http::Dl-Limit "70";
'
echo "$PDPATCH" | patch -bN /etc/apt/apt.conf.d/50unattended-upgrades
PDPATCH='
*** 50unattended-upgrades       2010-12-15 22:04:32.893507001 +0000
--- 50unattended-upgrades.good  2011-04-24 03:13:09.682787880 +0000
***************
*** 22,32 ****
  
  // Do automatic removal of new unused dependencies after the upgrade
  // (equivalent to apt-get autoremove)
! //Unattended-Upgrade::Remove-Unused-Dependencies "false";
  
  // Automatically reboot *WITHOUT CONFIRMATION* if a 
  // the file /var/run/reboot-required is found after the upgrade 
! Unattended-Upgrade::Automatic-Reboot "false";
  
  
  // Use apt bandwidth limit feature, this example limits the download
--- 22,32 ----
  
  // Do automatic removal of new unused dependencies after the upgrade
  // (equivalent to apt-get autoremove)
! /Unattended-Upgrade::Remove-Unused-Dependencies "false";
  
  // Automatically reboot *WITHOUT CONFIRMATION* if a 
  // the file /var/run/reboot-required is found after the upgrade 
! Unattended-Upgrade::Automatic-Reboot "true";
  
  
  // Use apt bandwidth limit feature, this example limits the download
'
echo "$PDPATCH" | patch -bN /etc/apt/apt.conf.d/50unattended-upgrades

echo "Patching gwc directory"
PDPATCH=' *** web.xml.orig	2011-04-22 13:02:04.000000000 +0000
--- web.xml	2011-05-09 10:27:51.002911979 +0000
***************
*** 57,63 ****
      <!-- Change the geowebcache dir -->
      <context-param>
        <param-name>GEOWEBCACHE_CACHE_DIR</param-name>
!       <param-value>/mnt/geowebcache</param-value>
      </context-param>
    
      <!-- pick up all spring application contexts -->
--- 57,63 ----
      <!-- Change the geowebcache dir -->
      <context-param>
        <param-name>GEOWEBCACHE_CACHE_DIR</param-name>
!       <param-value>/var/lib/tomcat6/webapps/geoserver/data/gwc</param-value>
      </context-param>
    
      <!-- pick up all spring application contexts -->
'
echo "$PDPATCH" | patch -bN /var/lib/tomcat6/webapps/geoserver/WEB-INF/web.xml

echo "Installing security patches -- this may reboot at end"
aptitude safe-upgrade -o Aptitude::Delete-Unused=false --assume-yes --target-release `lsb_release -cs`-security



