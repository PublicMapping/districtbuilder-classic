#!/bin/bash -x

#
# This changes the signup button to an e-mail link.
# Note it does not prevent users from signing up by their own and should not be used for security. 
# 

SUPPORTEMAIL=support@districtbuilder.org
PDPATCH="*** ../django/publicmapping/templates/index.html	2010-10-28 01:03:05.000000000 +0000
--- tmp	2010-10-28 01:08:14.000000000 +0000
***************
*** 120,126 ****
  
            <h4>To Draw Your Own Maps...</h4>
  
! 		<button  onclick=\"\$('#register').dialog('open');\" id=\"sign_up\" />Sign Up</button>
  
            <h4>To View Other Users' Maps...</h4>
  
--- 120,126 ----
  
            <h4>To Draw Your Own Maps...</h4>
  
! <a href=\"mailto:$SUPPORTEMAIL?subject=%5BDistrictBuilder%5D%20Account%20Request&body=Please%20create%20an%20account%20for%20districtbuilder%20\"><button id=\"sign_up\" />Sign Up</button></a>
  
            <h4>To View Other Users' Maps...</h4>
 " 
echo "$PDPATCH" | patch -bN /projects/PublicMapping/DistrictBuilder/django/publicmapping/templates/index.html
