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
       This script file defines behaviors of the share plan tab.
   
   Author: 
        Andrew Jennings, David Zwarg
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * sharing/publishing plans.
 *
 * Parameters:
 *   options -- Configuration options for the dialog.
 */
publishplan = function(options) {

    var _self = {},
        _options = $.extend({
            target: {},
            container: {},
            callback: function() {},
            autoOpen: false,
            modal: true,
            width:600
        }, options),
        // bunch o variables
        
        _nameRequired,
        _editType,
        _selectionType,
        _dialog;

    /**
     * Initialize the publisher. Load the publisher's contents and set up
     * the dialog.
     *
     * Returns:
     *   The publisher.
     */
    _self.init = function() {
        _options.container.load('/districtmapping/plan/' + PLAN_ID + '/publish/', function() { 
            setUpTarget();
            setUpEvents();
            
            _options.callback();
        });
        
        return _self;
    };
    
    /**
     * Show the dialog. This function is called from within the init
     * function's load callback.
     */
    var setUpTarget = function() {
        $('#PlanPublisher').dialog(_options);
        _options.target.click( function() {
            $('#PlanPublisher').dialog('open');
            loadButtons();
        });
    };

    /**
     * Set up the events and configure the publisher for operation. This
     * function is called from within the init function's load callback.
     */
    var setUpEvents = function() {
        $('#btnPublishPlan').click( function() {
            notImplemented();
        });

        $('#btnSubmitPlan').click( function() {
            notImplemented();
        });

        $('#btnClose').click(_close);

        
        var notImplemented = function() {
            $('<div class="error" title="Sorry">This feature has not yet been implemented. Stay tuned.</div>)').dialog({
                autoOpen:true,
                modal:true
            });
        };

    };

    /**
     * Close the publisher dialog.
     */
    var _close = function() {
        $('#PlanPublisher').dialog('close');
    };

    return _self;
};

