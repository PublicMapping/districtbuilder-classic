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
districtfile = function(options) {

    var _self = {},
        _options = $.extend({
            target: {},
            callback: function() {},
            /* the id for the plan to which this checker applies. by default, the current plan */
            planId: PLAN_ID,
            /* how often (in milliseconds) to check the index file status */
            timer: 15000, 
            /* The url to check the server for the status of the file */
            statusUrl: '/districtmapping/plan/' + ( typeof(options.planId) != 'undefined' ? options.planId : PLAN_ID ) + '/districtfilestatus/',
             /* The url to fetch the district index file */
            fetchUrl:'/districtmapping/plan/' + ( typeof(options.planId) != 'undefined' ? options.planId : PLAN_ID ) + '/districtfile/',
            /* The type of file to check/request: index or shape */
            type: 'index',
            /* Is this a menu item or a button? */
            menu_icon: null,
            /* Display Text for D/L Buttons */
            display: 'Index'
        }, options),
        
        _autoDownload = false,
        _visiblyUpdate = true;
        _checkInProgress = {};
     
    /**
     * Initialize the publisher. Load the publisher's contents and set up
     * the dialog.
     *
     * Returns:
     *   The publisher.
     */
    _self.init = function() {
        if (_visiblyUpdate) {
            if (options.menu_icon == null) {
                _options.target.empty();
                _options.target.append($('<div class="loading"></div>').width('70').height('25'));
            }
            else {
                _options.target.click(function(){
                    _autoDownload = true;
                    $.post(_options.fetchUrl + '?type=' + _options.type, indicatePending());
                    return false;
                });
            }

        }
        $.ajax({
           url: _options.statusUrl + '?type=' + _options.type,
           dataType: 'json',
           success: statusRequestCallback,
           error: function(xhr, textStatus, message) {
               if (xhr.status == 403) {
                   window.location.href='/?msg=logoff';
               }
           }
        });
        _options.callback();
        
        return _self;
    };
    
    /**
     * The callback after getting the status of the file
     */
    var statusRequestCallback = function(data) {
        if (data !== null && data.success) {
            var fileStatus = data.status,
                button;
            if (_options.type == 'index') {
                button = $('<button type="button" id="btnExportDistrictIndexFile" class="button" />');
            }
            else {
                button = $('<button type="button" id="btnExportDistrictShapeFile" class="button" />');
            };
            

            
            // If the file is ready, add a button/link to download
            if (fileStatus == 'done') {
                if (_autoDownload) {
                    window.location = _options.fetchUrl + '?type=' + _options.type;
                    _autoDownload = false;
                }
                if (_visiblyUpdate) {
                    if (_options.menu_icon != null) {
                        $('.ui-icon', _options.target).css('background-image','url("'+_options.menu_icon+'")');
                        _options.target.unbind('click');
                        _options.target.click(function(){
                            window.location = _options.fetchUrl + '?type=' + _options.type;
                            return false;
                        });
                    }
                    else {
                        _options.target.empty();
                        var link = $('<a href="' + _options.fetchUrl + '?type=' + _options.type + '" />');
                        button.text(gettext('Download '+_options.display)).button();
                        $(link).append(button);
                        _options.target.append(link);    
                    }
                }
            // If the file is in progress, show that
            } else if (fileStatus == 'pending') {
                indicatePending();
            // Else let the user request the file, then move to pending
            } else if (fileStatus == 'none') {
                if (_visiblyUpdate) {
                    if (_options.menu_icon == null) {
                        _options.target.empty();
                        button.text(gettext('Request '+_options.display)).button();
                        button.click(function(){
                            _autoDownload = true;
                            $.post(_options.fetchUrl + '?type=' + _options.type, indicatePending());
                            return false;
                        });
                        _options.target.append(button);
                    }
                }
            }
        } else {
            if ('redirect' in data) {
                window.location.href = data.redirect;
            }
        }
    };

    /** 
     * Show the loading indicator.  If the file is loaded totally, show 
     * a button to download the file
     */
    var indicatePending = function() {
        if (_visiblyUpdate && !_options.target.children().hasClass('pending')) {
            if (_options.menu_icon != null) {
                $('.ui-icon', _options.target).css('background-image','url("/static/images/share-loading.gif")');
            }
            else {
                _options.target.empty();
                var pending = $('<div id="pendingMessage" class="loading" />');
                pending.text(gettext('Please wait. File is being created on the server'));
                _options.target.append(pending);
            }
        }
        
        // Request the status again after the timer time has passed
        var checkagain = function() {
            $.post(_options.statusUrl + '?type=' + _options.type, statusRequestCallback);
        };
        _checkInProgress = setTimeout(checkagain, _options.timer);
    };

    /**
     * Clear out the setTimeout item that checks for the file status
     */
    _self.stopChecking = function() {
        clearTimeout(_checkInProgress);
        return _self;
    };
    
    /**
     * Set whether this publisher should automatically update UI items
     * when checking the status in the background
     */
    _self.setUpdateVisibility = function(visible) {
        _visiblyUpdate = visible;
        return _self;
    }

    return _self;
};

