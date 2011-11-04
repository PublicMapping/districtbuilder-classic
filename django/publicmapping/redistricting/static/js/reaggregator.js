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
       This script file defines behavior necessary for reaggregating plans
   
   Author: 
        Andrew Jennings, David Zwarg, Kenny Shepard
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * reaggregating a plan.
 *
 * Parameters:
 *   options -- Configuration options for the reaggregator
 */
reaggregator = function(options) {
    var _self = {},
        _options = $.extend({
            // How often (in milliseconds) to check for status updates
            timerInterval: 5000, 

            // The url to check the server for the status of reaggregation
            statusUrl: '/districtmapping/processingstatus/',

            // Anonymous users can only view plans (and need different button text)
            anonymous: false,

            // jqGrid object: so refreshes can be triggered
            grid: $('#plan_table'),

            // Tabs object: so we only query for status when viewing the plan chooser
            tabs: $('#steps')
        }, options),

        // Mapping of id -> state for last returned data state
        _currData,

        // Current filter ('Plan Type' tab selection)
        _filterId,

        // Currently selected tab. Only query status when Plan (index=0) is selected
        _tabId,

        // If the user selects "Reaggregate and Start Drawing', the plan id gets
        // added to this array. When new reaggregation statuses come in, and an id 
        // in this array has a state of 'Ready', user is navigated to the plan page.
        _reaggregatingIds = [];

    /**
     * Initializes the reaggregator. 
     *
     * Returns:
     *   The reaggregator.
     */
    _self.init = function() {
        // Set the initial tab state
        _tabId = _options.tabs.tabs('option', 'selected');

        // Listen for tab changes
        _options.tabs.bind('tabSelected', function(event, tabIndex) {
            _tabId = tabIndex;
        });

        // Start the timer that checks for status
        setInterval(function() {
            if (!_currData || _tabId) {
                return;
            }

            // Assemble list of ids to check for. That's all of the current 
            // ones, plus any other ones the user asked for reaggregation.
            var planIds = [];
            $.each(_currData, function(id) {  planIds.push(parseInt(id, 10)); });
            $(_reaggregatingIds).each(function(i, planId) {
                if ($.inArray(planId, planIds) < 0) {
                    planIds.push(planId);
                }
            });

            $.ajax({
                url: _options.statusUrl,
                type: 'GET',
                data: { planIds: planIds },
                success: function(data) {
                    if (data.success) {
                        updateData(data.message);
                    }
                },
                error: function() {
                    $('<div class="error" title="Sorry">Error getting plan status</div>')
                        .dialog({modal:true, resizable:false});
                }
            });
        }, _options.timerInterval)
    };
    
    /**
     * Updates the display for the currently selected plan
     */
    _self.planSelected = function(planId) {
        // TODO: update buttons/etc.
    };

    /**
     * Updates the set of plan ids that are being watched for status
     */
    _self.dataUpdated = function(data) {
        var newData = {};
        $(data.rows).each(function(i, row) {
            newData[row.pk] = row.fields.processing_state;
        });
        updateData(newData);
    };

    // Do the data update -- called from both dataUpdated,
    // and ajax status check, after data is unified.
    var updateData = function(newData) {
        // No extra processing needed on first pass-through
        if (!_currData) {
            _currData = newData;
            return;
        } 

        // Check if any plans in which reaggregation was requested
        // have completed. If so, redirect to the plan page.
        $(_reaggregatingIds).each(function(i, planId) {
            if (newData[i] === 'Ready') {
                window.location = '/districtmapping/plan/' + planId + '/edit/';
            }
        });

        // Check if any statuses have changed. If so, force a grid refresh.
        var changed = false;
        $.each(newData, function(id, newStatus) {
            var oldStatus = _currData[id];
            if (oldStatus && (oldStatus !== newStatus)) {
                changed = true;
            }
        });
        if (changed) {
            _options.grid.trigger('reloadGrid');
        }

        // Update the stored data
        _currData = newData;
    };

    /**
     * Updates the current filter ('Plan Type' selection)
     */
    _self.filterChanged = function(filterId) {
        _filterId = filterId
    };

    return _self;
};
