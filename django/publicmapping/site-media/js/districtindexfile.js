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
   http://sourceforge.net/projects/publicmapping/

   Purpose:
       This script file defines behavior necessary for export district index files
   
   Author: 
        Andrew Jennings, David Zwarg
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * exporting the district index files.
 *
 * Parameters:
 *   options -- Configuration options for the dialog.
 */
districtindexfile = function(options) {

    var _self = {},
        _options = $.extend({
            target: {},
            callback: function() {},
            /* the id for the plan to which this checker applies. by default, the current plan */
            planId: PLAN_ID,
            /* how often (in milliseconds) to check the index file status */
            timer: 15000, 
            /* The url to check the server for the status of the file */
            statusUrl: '/districtmapping/plan/' + ( typeof(options.planId) != 'undefined' ? options.planId : PLAN_ID ) + '/districtindexfilestatus/',
             /* The url to fetch the district index file */
            fetchUrl:'/districtmapping/plan/' + ( typeof(options.planId) != 'undefined' ? options.planId : PLAN_ID ) + '/districtindexfile/'
        }, options);
     
    /**
     * Initialize the publisher. Load the publisher's contents and set up
     * the dialog.
     *
     * Returns:
     *   The publisher.
     */
    _self.init = function() {
        $.post(_options.statusUrl, statusRequestCallback);
        _options.callback();
        
        return _self;
    };
    
    /**
     * The callback after getting the status of the file
     */
    var statusRequestCallback = function(data) {
        if (data.success) {
            var fileStatus = data.status;
            // If the file is ready, add a button/link to download
            if (fileStatus == 'done') {
                _options.target.empty();
                var link = $('<a href="' + _options.fetchUrl + '" />');
                var button = $('<button id="btnExportDistrictIndexFile" class="button">Download</button>').button();
                $(link).append(button);
                _options.target.append(link);    
                $(link).click();
            // If the file is in progress, show that
            } else if (fileStatus == 'pending') {
                indicatePending(data);
            // Else let the user request the file, then move to pending
            } else if (fileStatus == 'none') {
                _options.target.empty();
                var button = $('<button id="btnExportDistrictIndexFile" class="button">Request File</button>').button();
                button.click( function() {
                    $.post(_options.fetchUrl, indicatePending(data));
                });
                _options.target.append(button);    
            }
        }
    };
    /**
     * The callback after the initial attempt to get a district index file
     * If the user has not defined an email address, they'll be asked to 
     * supply one to which the district index file can be mailed
     */
    var fileRequestCallback = function(data) {
        if (data.success) {
            successfulSend(data);
        } else {
            if (data.askforemail) {
                askForEmail();
            }
        }
    };

    /** 
     * Show the loading indicator.  If the file is loaded totally, show 
     * a button to download the file
     */
    var indicatePending = function(data) {
        if (!_options.target.children().hasClass('pending')) {
            _options.target.empty();
            var pending = $('<div id="pendingMessage" class="loading">Please wait. File is being created on the server.</div>');
            _options.target.append(pending);
        }
        
        // Request the status again after the timer time has passed
        var checkagain = function() {
            if ($('#steps').tabs('option', 'selected') == 3) {
                $.post(_options.statusUrl, statusRequestCallback);
            }
        };
        setTimeout(checkagain, _options.timer);
    };

    /**
     * The callback for a successful send.  Let the user know that the
     * file will come via email.
     */
    var successfulSend = function(data) {
        $('<div title=\'Exporting\'>' + data.message + '</div>').dialog({
             modal:true,
             resizable:false
        });
    };
    

    /**
     * If the user has no email address, this dialog will give them the opportunity
     * to supply one to which a district index file can be mailed.
     */
    var askForEmail = function() {
        // Clean up any old dialogs that are in the DOM
        $('#dlgMail').remove();
        var dlgMail = $("<div id='dlgMail'><div>Please suppy a valid email address so we " + 
            "can email the file to you. The address won't be saved or shared.</div><input id='email' type='text' /></div>");
        dlgMail.dialog({
            modal:true,
            resizable:false,
            title: 'Email address needed',
            buttons: {
                'Email Me': function() {
                    // Check for a properly formatted email address first
                    var address = $('#dlgMail #email').val();
                    if (!(address.match(/^([\w\-\.\+])+\@([\w\-\.])+\.([A-Za-z]{2,4})$/))) {
                        if ($('#dlgMail .error').length == 0) {
                            $('#dlgMail input').css('border', '1px solid #ff0000');
                            $('#dlgMail input').before($("<div class='error'>That is not a valid email address.</div>"));
                        }
                    } else {
                        $.post('/districtmapping/plan/' + PLAN_ID + '/districtindexfile/', { email: address }, fileRequestCallback);
                        $('#dlgMail').dialog('close');
                    }
                },
                'No thanks': function() {
                    $('#dlgMail').dialog('close');
                }
            }
        });
    };

    return _self;
};

