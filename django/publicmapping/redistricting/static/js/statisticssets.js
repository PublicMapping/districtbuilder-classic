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
       This script file defines behavior necessary for the stats picker
        on the demographics tab
   
   Author: 
        Andrew Jennings, David Zwarg, Kenny Shepard
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * exporting the district index files.
 *
 * Parameters:
 *   options -- Configuration options for the dialog.
 */
statisticssets = function(options) {

    var _self = {},
        _options = $.extend({
            target: $('#open_statistics_editor'),
            container: $('#stats_editor_container'),
            selector: {},
            callback: function() {},
            /* the id for the plan to which this checker applies. by default, the current plan */
            statsUrl: '/districtmapping/plan/' + ( typeof(options.planId) != 'undefined' ? options.planId : PLAN_ID ) + '/statisticssets/',
            loadDemographicsUrl: '/districtmapping/plan/' + ( typeof(options.planId) != 'undefined' ? options.planId : PLAN_ID ) + '/demographics/',
        }, options),
        
        _selector = $('#map_menu_header > select'),
        _personalDisplayId,
        _allPersonalDisplaysIds,
        _selectedScoreFunctionIds,
        _allScoreFunctionIds,
        _clearButton = $('#clear_statistics');
        _functionsContainer = $("#available_statistics"),
        _saveButton = $("#save_statistics_set"),
        _statisticsSetNameField = $("#statistics_set_name"),
        _savedSetsContainer = $("#saved_statistics_sets");
     
    /**
     * Initialize the publisher. Load the publisher's contents and set up
     * the dialog.
     *
     * Returns:
     *   The publisher.
     */
    _self.init = function() {
        _options.container.hide();
        _options.target.click( function() {_options.container.dialog({ width: 500 }); });
        _selector.change( showScoreDisplay );
        $.ajax({
           url: _options.statsUrl,
           dataType: 'json',
           success: statsRequestCallback,
           error: function(xhr, textStatus, message) {
               if (xhr.status == 403) {
                   window.location.href='/?msg=logoff';
               }
           }
        });
        initButtons();
        _options.callback();
        
        return _self;
    };
    
    /**
     * Sets up the click event for the save button
     */
    var initButtons = function() {
        _saveButton.click(function() {
            var name = _statisticsSetNameField.val();
            var selection = [];
            _savedSetsContainer.find(':checked').each( function() {
                selection.push($(this).children('input').val());
            });
            saveStatisticsSet(name, selection);
        });
        _clearButton.click(function() {
            $('.function').each( function() {
                $(this).attr('checked', false);
            });
            _statisticsSetNameField.val('');
        });
    };
    /**
     * The callback after getting the initial info to populate
     * the UI
     */
    var statsRequestCallback = function(data) {
        if (data.success) {
            for (i in data.sets) {
                var set = data.sets[i];
                addSetToSelector(set);
                var button = createStatisticsSetButton(set);
                _savedSetsContainer.append(button);
            }
            for (i in data.functions) {
                var func = data.functions[i];
                var option = createFunctionElement(func);
                _functionsContainer.append(option);
            }
        } else {
            if ('redirect' in data) {
                window.location.href = data.redirect;
            }
        }
    };

    var showScoreDisplay = function(event) {
        var displayId = $(this).val();
        $('.demographics').load(
            _options.loadDemographicsUrl,
            {
                displayId: displayId
            },
            function(rsp, status, xhr) {
                if (xhr.status > 400) {
                    window.location.href = '/';
                }
                else {
                    loadTooltips();
                    // sortByVisibility(true);
                }
            }
        );  
        // alert("Should load display " + displayId);
    }
    /**
     * Given a function object in JSON, create a checkbox and
     * name combo for insertion into the statistics set editor
     */
    var createFunctionElement = function(func) {
        var funcId = 'function_' + func.id;
        var div = $('<div class="function_wrapper"></div>');
        var input = $('<input class="function" id="' + funcId + '" value="' + func.id + '" type="checkbox"></input>');
        var label = $('<label for="' + funcId + '">' + func.name + '</label>');
        div.append(input);
        div.append(label);
        return div;
    };

    /**
     * Given a statistics set as a JSON object, create the clickable
     * button that allows users to edit or delete their personal
     * statistics sets.
     *
     * Returns a jQuery object representing the clickable DOM element
     */
    var createStatisticsSetButton = function(set) {
        if (set.functions.length == 0) return false;
        var set_button = $('<div id="select_statistics_set_' + set.id + '" class="statistics_set"></div>');
        set_button.append(set.name);
        set_button.data('name', set.name);
        set_button.data('functions', set.functions);
        set_button.bind('click', {set: set}, selectSet);

        var deleteButton = $('<button id="delete_set_' + set.id + '" class="delete_set"></button>');
        deleteButton.data('id', set.id);
        deleteButton.bind('click', { id: set.id}, deleteSet);
        deleteButton.button({icons: {primary: 'icon-trash'}, text: false});
        set_button.append(deleteButton);

        return set_button;
    };

    /**
     * Adds an entry for the given statistics set to the 
     * dropdown so the user can view the stats set
     */
    var addSetToSelector = function(set, select) {
        _selector.append($('<option value="' + set.id + '">' + set.name + '</option>'));
        if (select) {
            showStatisticsSet(set.id);
        }
    };

    var showStatisticsSet = function(id) {
        _selector.val(id);
        _selector.trigger('change');
        _options.container.dialog("close");
    }

    /**
     * Removes an entry for the given statistics set
     * from the dropdown selector and buttons
     */
    var deleteFromUI = function(set) {
        _selector.children().remove('option[value="' + set.id + '"]');
        _savedSetsContainer.children().remove('#select_statistics_set_' + set.id);
    };

    /**
     * Given a statistic set's ID, delete the stats set
     */
    var deleteSet = function(event) {
        if (event.data) {
            data = event.data
            data['delete'] = true
            $.ajax({
                url: _options.statsUrl,
                type: 'POST',
                data: event.data,
                success: function(data) {
                    if (data.success == true) {
                        deleteFromUI(data.set);
                    }
                }
            });
        }
        return false; /* don't want selection event to occur, too */
    };

    /**
     * Given a statistics set, populate the scrollable list of 
     * ScoreFunctions to indicate which ones are included in the
     * just-selected Statistics Set. Populate the name field to 
     * indicate which set is being edited.
     */
    var selectSet = function(event, data, whatever, something) {
        var set = event.data.set;
        _statisticsSetNameField.val(set.name);
        $('.function').each( function() {
            var id = parseInt($(this).val());
            var index = set.functions.indexOf(id);
            var checked = index > -1 ? true : false;
            $(this).attr('checked', checked);
        });
    };

    /**
     * Gets an array of IDs representing the selected ScoreFunctions
     */
    var getSelectedScoreFunctions = function() {
        var checked = _functionsContainer.find(':checked');
        var functions = [];
        checked.each( function() {
            functions.push($(this).val());
        });
        return functions;
    };

    /** 
     * Save the Statistics Set. The backend will decide whether a 
     * new set is required or the current set is edited.
     */
    var saveStatisticsSet = function(name, selectedStats) {
        
        var functionArray = getSelectedScoreFunctions();
        if (functionArray.length > 3) {
            $("<div>Please select 3 or fewer statistics.</div>").dialog({
                title: 'Error',
                resizable:false,
                modal:true
            });
            return false;
        }
        var data = { functions: functionArray, name: _statisticsSetNameField.val() };
        $.ajax({
            type: 'POST',
            data: data,
            url: _options.statsUrl,
            success: function(data) {
                if (data.success == true) {
                    if (data.newRecord == true) {
                        var record = createStatisticsSetButton(data.set);
                        _savedSetsContainer.append(record);
                        addSetToSelector(data.set, true);
                    } else {
                        showStatisticsSet(data.set.id);
                    }
                } else {
                    if (data.error == 'limit') {
                        $('<div>' + data.message + '</div>').dialog({
                            title: 'Error',
                            resizable:false,
                            modal:true
                        });
                    }
                }
            }
        });
    };

    return _self;
};
