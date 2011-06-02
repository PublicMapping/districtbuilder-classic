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
       This script file defines behaviors of the 'Splits Report' dialog
   
   Author: 
        Andrew Jennings, David Zwarg, Kenny Shepard
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * generating splits reports
 *
 * Parameters:
 *   options -- Configuration options for the splits report tool.
 */
splitsreport = function(options) {
    var _self = {},
        _options = $.extend({
            container: {},
            target: {},
            okButton: {},
            inverseCheckbox: {},
            availableLayers: {},
            referenceLayerSelect: {},
            splitsReportUrl: {},
            resultsContainer: {},
            map: {},
            getVersionFn: {},
            autoOpen: false,
            modal: true,
            width: 800,
            height: 'auto',
            title: 'Splits Report',
            resizable: false,
            closable: true
        }, options);

    /**
     * Initialize the splits report tool. Setup the click event for the target to
     * show the splits report tool.
     *
     * Returns:
     *   The splits report tool.
     */
    _self.init = function() {
        _options.container.dialog(_options);
        _options.target.click(showDialog);

        // Add button behavior for displaying reports
        var displaySplits = function(ids) {
            console.debug();
            
            var waitDialog = $('<div>Please wait while retrieving splits report.</div>').dialog({
                modal: true,
                autoOpen: true,
                title: 'Retrieving Splits Report',
                escapeOnClose: false,
                resizable:false,
                open: function() { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); }                    
            });
    
            $.ajax({
                type: 'GET',
                url: _options.splitsReportUrl,
                data: {
                    version: _options.getVersionFn(),
                    layers: ids,
                    inverse: _options.inverseCheckbox.is(':checked')        
                },
                success: function(data, textStatus, xhr) {
                    waitDialog.remove();
                    _options.resultsContainer.html(data);
                },
                error: function(xhr, textStatus, error) {
                    waitDialog.remove();                        
                    $('<div>Error encountered while retrieving splits report: ' + textStatus + '</div>').dialog({
                        modal: true, autoOpen: true, title: 'Error', resizable:false
                    });                
                }
            });
        };
        _options.okButton.click(function(){
            var selected = [];
            _options.availableLayers.find(':checked').each( function() {
                selected.push($(this).val());
            });
            if ((selected.length < 1) || (selected.length > 3)) {
                $("<div>Please select either 1, 2, or 3 layers for comparison.</div>").dialog({
                    title: 'Warning',
                    resizable:false,
                    modal:true
                });
                return false;
            }
            displaySplits(selected);
        });

        // Listen for new 'converted' layers to add as selectable options
        _options.map.bind('reference_layer_changed', function(evt, rid, rname) {
            // Uncheck all checked items
            _options.availableLayers.find(':checked').prop('checked', false);

            // Don't do anything if it's 'None'
            if (rid === 'None') {
                return;
            }
      
            // Only add the option if it hasn't already been added
            if (_options.availableLayers.find('input[id=' + rid.replace('.', '\\.') + ']').length === 0) {
                var div = $('<div class="layer_choice_wrapper"></div>');
                div.append($('<input class="layer_choice" id="' + rid + '" value="' + rid + '" type="checkbox"></input>'));
                div.append($('<label for="' + rid + '">&nbsp;' + rname + '</label>'));
                _options.availableLayers.append(div);            
            }

            // Check the selected item
            $('#' + rid.replace('.', '\\.')).prop('checked', true);
        });
    };

    /**
     * Display the dialog
     */
    var showDialog = function() {
        _options.container.dialog('open');
    };

    return _self;
};
