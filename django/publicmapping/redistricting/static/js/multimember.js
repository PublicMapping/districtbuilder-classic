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
 * assigning members to districts
 *
 * Parameters:
 *   options -- Configuration options for the assignment tool.
 */
multimember = function(options) {

    var _self = {},
        _options = $.extend({
            container: {},
            memberGrid: {},
            numMembersContainer: {},
            numMultiDistsContainer: {},
            targetMembersContainer: {},
            targetMultiDistsContainer: {},
            targetMembersPerDistContainer: {},
            minMultiDistricts: {},
            maxMultiDistricts: {},
            minMultiDistrictMembers: {},
            maxMultiDistrictMembers: {},
            minPlanMembers: {},
            maxPlanMembers: {},
            target: {},
            assignButton: {},
            workingDialog: {},
            getDistrictsFn: {},
            getVersionFn: {},
            handlerUrl: '',
            autoOpen: false,
            modal: true,
            width: 650,
            title: gettext('Set Multi-Member Districts'),
            resizable: false,
            closable: true
        }, options);

    /**
     * Initialize the assignment tool. Setup the click event for the target to
     * show the assignment tool.
     *
     * Returns:
     *   The assignment tool.
     */
    _self.init = function() {
        _options.container.dialog(_options);
        initTargets();
        initSaving();
        initGrid();
        _options.target.click(showDialog);
    };

    // Recreate dynamic components each time the dialog is shown, as districts
    // may be available/removed each time
    var showDialog = function() {
        _options.container.dialog('open');

        // Empty the grid
        var rowIds = $(_options.memberGrid).jqGrid('getDataIDs');
        for(var i = 0, len = rowIds.length; i < len; i++){
            $(_options.memberGrid).jqGrid('delRowData', rowIds[i]);
        }   

        // Populate the grid
        var sortedDistricts = $(_options.getDistrictsFn()).sort(function(d1, d2){ return d1.district_id > d2.district_id; });
        sortedDistricts.each(function(i, district) {
            $(_options.memberGrid).jqGrid('addRowData', i+1, {
                name: district.label,
                num_members: district.num_members,
                district_id: district.district_id        
            });
        });

        // Update the statistics
        updateStats();
    };

    // Update the number of members and number of multi-member districts
    var updateStats = function() {
        // Accumulate stats
        var numMembers = 0;
        var numMultiDists = 0;
        var rows = $(_options.memberGrid).jqGrid('getRowData');
        for(var i = 0; i < rows.length; i++){
            var row = rows[i];
            var num = parseInt(row.num_members, 10);

            numMembers += num;
            if (num > 1) {
                numMultiDists += 1;
            }
        }

        var invalidDistricts = false, invalidMembers = false
        // Populate num members
        $(_options.numMembersContainer).html(numMembers);
        if ((numMembers >= _options.minPlanMembers) && (numMembers <= _options.maxPlanMembers)) {
            $(_options.numMembersContainer).addClass('valid');
            $(_options.numMembersContainer).removeClass('invalid');
            $(_options.numMembersContainer).parent().removeClass('invalid')
        } else {
            invalidMembers = true;
            $(_options.numMembersContainer).addClass('invalid');
            $(_options.numMembersContainer).parent().addClass('invalid')
            $(_options.numMembersContainer).removeClass('valid');
        }

        // Populate num multi-member districts
        $(_options.numMultiDistsContainer).html(numMultiDists);
        if ((numMultiDists >= _options.minMultiDistricts) && (numMultiDists <= _options.maxMultiDistricts)) {
            $(_options.numMultiDistsContainer).addClass('valid');
            $(_options.numMultiDistsContainer).removeClass('invalid');
            $(_options.numMultiDistsContainer).parent().removeClass('invalid')
        } else {
            invalidDistricts = true;
            $(_options.numMultiDistsContainer).addClass('invalid');
            $(_options.numMultiDistsContainer).parent().addClass('invalid')
            $(_options.numMultiDistsContainer).removeClass('valid');
        }

        if (invalidMembers || invalidDistricts) {
            $(_options.assignButton).button('disable');
        } else {
            $(_options.assignButton).button('enable');
        }
    };

    // Set up targets
    var initTargets = function() {
        var text;

        // Target # of representatives
        if (_options.minPlanMembers === _options.maxPlanMembers) {
            text = _options.minPlanMembers;
        } else {
            text = _options.minPlanMembers + ' - ' +  _options.maxPlanMembers;
        }
        $(_options.targetMembersContainer).html(text);

        // Target # of multi-member districts
        if (_options.minMultiDistricts === _options.maxMultiDistricts) {
            text = _options.minMultiDistricts;
        } else {
            text = _options.minMultiDistricts + ' - ' +  _options.maxMultiDistricts;
        }
        $(_options.targetMultiDistsContainer).html(text);

        // Target # of members per multi-member district
        if (_options.minMultiDistrictMembers === _options.maxMultiDistrictMembers) {
            text = _options.minMultiDistrictMembers;
        } else {
            text = _options.minMultiDistrictMembers + ' - ' +  _options.maxMultiDistrictMembers;
        }
        $(_options.targetMembersPerDistContainer).html(text);
    };
    
    // Set up save functionality
    var initSaving = function() {
        _options.assignButton.click( function() {
            // Obtain district member data from the grid
            var districts = [];
            var counts = [];
            var rows = $(_options.memberGrid).jqGrid('getRowData');
            for(var i = 0; i < rows.length; i++){
                var row = rows[i];
                districts.push(parseInt(row.district_id, 10));
                counts.push(parseInt(row.num_members, 10));
            }

            // Post the district member data
            $.ajax({
                url: _options.handlerUrl,
                type: 'POST',
                data: {
                    districts: districts,
                    counts: counts,
                    version: _options.getVersionFn()
                },
                success: function(data) {
                    $(_options.workingDialog).dialog('close');
                    if (data.success) {
                        if (data.modified) {
                            var updateAssignments = false;
                            $('#map').trigger('version_changed', [data.version, false]);
                        }
                    } else {
                        $('<div class="error" />').attr('title', gettext('Sorry'))
                            .text(gettext('Unable to assign representatives:') + data.message)
                            .dialog({modal:true, resizable:false});
                    }
                },
                error: function() {
                    $('<div class="error" />').attr('title', gettext('Sorry'))
                        .text(gettext('Unable to assign representatives'))
                        .dialog({modal:true, resizable:false});
                }
            });
            _options.container.dialog('close');
            $(_options.workingDialog).dialog('open');
        });
    };
    
    // Set up grid
    var initGrid = function() {
        // Storage for the last selected id
        var lastId;

        // Use custom validation
        var validate = function(newVal) {
            // Validate on a timer, to allow jqgrid to finish its local save first
            setTimeout(function() {
                var val = parseInt(newVal, 10);
                var min = _options.minMultiDistrictMembers;
                var max = _options.maxMultiDistrictMembers;
                    
                // Check for good value -- either 1 or within multi member range
                if (!isNaN(newVal) && ((val === 1) || (val >= min) && (val <= max))) {
                    // Valid - update the counts
                    updateStats();
                } else {
                    // Invalid - revert to 1 and return to edit mode
                    var rows = $(_options.memberGrid).jqGrid('getRowData');
                    var rowObject = rows[lastId - 1];
                    rowObject.num_members = 1;
                    $(_options.memberGrid).jqGrid('setRowData', lastId, rowObject);

                    // Update counts first, since it's possible to escape out of the edit
                    updateStats();
                    $(_options.memberGrid).jqGrid('editRow', lastId, true);
                }
            }, 0);
            return [true, ''];
        };

        // Create the grid
        $(_options.memberGrid).jqGrid({
            datatype: 'local',
            colNames: [gettext('District'), gettext('District ID'), gettext('# Members')],
            colModel: [
                { name: 'name', index: 'district_id', width: 90, align: 'left', sorttype: 'int' },
                { name: 'district_id', index: 'district_id', hidden: true },
                { name: 'num_members', index: 'num_members', editable: true, 
                        width: 100, sorttype: 'int', align: 'right',
                        editrules: { custom: true, custom_func: validate }
                }
            ],
            editurl: 'clientArray',
            onSelectRow: function(id) {
                // Don't allow saving while in edit mode
                $(_options.assignButton).button('disable'); 
                    
                $(_options.memberGrid).jqGrid('restoreRow', lastId);
                $(_options.memberGrid).jqGrid('editRow', id, true);
                lastId = id;

                $("input[id^='" + id + "_num_members']", $(_options.memberGrid)).bind('blur',
                    function() { 
                        $(_options.memberGrid).saveRow(id);
                    }
                );
            }
        });
        $(_options.memberGrid).jqGrid('navGrid');
    };
    return _self;
};
