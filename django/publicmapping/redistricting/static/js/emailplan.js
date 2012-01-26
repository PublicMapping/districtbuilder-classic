/*
   Copyright 2010 Micah Altman, Michael McDonald

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

   This file is part of The Public Mapping Project
   https://github.com/PublicMapping/

   Purpose:
       This script file defines behaviors of the 'Assign Representatives' dialog
   
   Author: 
        Andrew Jennings, David Zwarg, Kenny Shepard
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * emailing a plan
 *
 * Parameters:
 *   options -- Configuration options for the email plan tool.
 */
emailplan = function(options) {

    var _self = {},
        _options = $.extend({
            container: {},
            target: {},
            submitButton: {},
            handlerUrl: '',            

            title: gettext('Submit Final Plan to Contest'),
            autoOpen: false,
            modal: true,
            width: 525,
            resizable: false,
            closable: true
        }, options);

    /**
     * Initialize the email plan tool. Setup the click event for the target to
     * show the email plan tool.
     *
     * Returns:
     *   The email plan tool.
     */
    _self.init = function() {
        _options.container.dialog(_options);
        _options.target.click(showDialog);
        _options.submitButton.click(submitForm);
    };

    // Show the dialog
    var showDialog = function() {
        _options.container.dialog('open');
    };

    // Validate form and submit to server for sending email
    var submitForm = function() {
        var values = {};
        var failedVerification = false;
        _options.container.find(".field").each(function(i, node) {
            var obj = $(node);
            var name = obj.prop('name');
            var val = obj.val();

            // Capture non-empty values
            if (val) {
                values[name] = val;
            }

            // Check for a valid email address
            if ((name === "email") && (!val.match(/^([\w\-\.\+])+\@([\w\-\.])+\.([A-Za-z]{2,4})$/))) {
                val = null;
            }

            // Check all required fields
            obj.removeClass("error");
            if (obj.hasClass("required") && !val) {
                failedVerification = true;
                obj.addClass("error");
            }
        });

        if (failedVerification) { return; }

        // Everything is valid, send a request to the server
        _options.container.dialog('close');
        var waitDialog = $('<div />').text(gettext('Please wait. Emailing plan.')).dialog({
            modal: true, autoOpen: true, title: gettext('Emailing Plan'),
            escapeOnClose: false, resizable:false,
            open: function() { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); }
        });
        
        $.ajax({
            type: 'POST',
            data: values,
            url: _options.handlerUrl,
            success: function(data) {
                waitDialog.remove();
                if (data.success) {
                    $('<div />').attr('title', gettext('Emailing Plan'))
                        .text(gettext('Your plan is in the process of being submitted. You will receive a confirmation email once it has completed successfully. This may take a few minutes.')).dialog({
                          modal:true, resizable:false,
                          buttons: [{
                            text: gettext("OK"),
                            click: function() { $(this).dialog('close'); }
                          }]
                      });
                } else if ('redirect' in data) {
                    window.location.href = data.redirect;
                } else if ('message' in data) {
                    $('<div />').attr('title', gettext('Error Emailing Plan')).text(data.message)
                        .dialog({modal:true, resizable:false});
                }
            },
            error: function(xhr, textStatus, message) {
                waitDialog.remove();
                if (xhr.status == 403) {
                    window.location.href = '/?msg=logoff';
                } else {
                    $('<div />').attr('title', gettext('Error Emailing Plan'))
                        .text(gettext('Please try again later')).dialog({modal:true, resizable:false});
                }
        }});
    };

    return _self;
};
