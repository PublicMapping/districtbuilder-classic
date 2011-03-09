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
       This script file defines behaviors of the 'Copy and Paste Districts' dialog
   
   Author: 
        Andrew Jennings, David Zwarg
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * displaying available plans and instantiating templates.
 *
 * Parameters:
 *   options -- Configuration options for the chooser.
 */
shareddistricts = function(options) {

    var _self = {},
        _options = $.extend({
            target: {},
            container: {},
            planTable: {},
            planPager: {},
            planUrl: '',
            districtTable: {},
            districtPager: {},
            // When putting in the district URL, make sure to add the PLAN_ID like so
            districtUrl: '/districtmapping/plan/PLAN_ID/shareddistricts/',
            handlerUrl: '',
            autoOpen: false,
            modal: true,
            width: 800,
            title: 'Copy and Paste Districts',
            resizable: false,
            closable: true
        }, options),
        // bunch o variables
       
        _container, 
        _planTable,
        _selectedPlanId,
        _nameRequired,
        _selectedDistricts,
        _selectedPlanName,
        _editButton,
        _saveButton,
        _cancelButton;

    /**
     * Initialize the chooser. Setup the click event for the target to
     * show the chooser.
     *
     * Returns:
     *   The chooser.
     */
    _self.init = function() {
        _options.container.dialog(_options);
        _options.target.click(function() { _options.container.dialog( 'open'); });

        _selectedDistricts = [];
        _planTable = _options.planTable;
        loadPlanTable();
        _districtTable = options.districtTable;
        loadDistrictsTable();

        initUI();
    };


    /**
     * Set up the jqGrid table and make the initial call to the server for data
     */
    var loadPlanTable = function() {
        _planTable.jqGrid({
            pager:_options.planPager,
            url:_options.planUrl,
            hidegrid: false,
            /* scroll: true, /* dynamically scroll grid instead of using pager */
            gridview: true,
            altRows: true,
            altclass: 'chooserAlt',

            datatype: 'json',
            jsonReader: {
                repeatitems: false,
                id: 'pk'
            },
            colModel: [
                {name:'fields.owner', label:'Author', search:true, width: '110', fixed: true, sortable:true},
                {name:'fields.name', label:'Plan', search: true, sortable:true},
                {name:'fields.description', label:'Description', hidden:true, search:true},
                {name:'fields.is_shared', label:'Shared', hidden:true, search:false, formatter:'checkbox', width:'70', fixed: true, align: 'center'},
                {name:'fields.edited', label:'Last Edited', sortable:true, search:false, width:'130', fixed: true, align: 'center', formatter:'date', formatoptions: { srcformat: 'UniversalSortableDateTime', newformat:'m/d/Y g:i A'}},
                {name:'fields.can_edit', label:'Edit', search:false, hidden: true},
                {name:'fields.districtCount', label:'# Districts', search:false, sortable:true, hidden:true}
            ],

            onSelectRow: planSelected,
            beforeRequest: appendExtraParamsToRequest,
            loadError: loadError,
            height: 'auto',
            autowidth: 'true',
            rowNum:15,
            sortname: 'id',
            viewrecords:true,
            mtype: 'POST',
            ajaxGridOptions: {
                beforeSend: function(xhr, settings) {
                    if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                        // Only send the token to relative URLs i.e. locally.
                        xhr.setRequestHeader("X-CSRFToken",
                                             $("#csrfmiddlewaretoken").val());
                    }
                }
            }
        }).jqGrid(
            'navGrid',
            '#' + _options.planPager.attr('id'),
            {search:false,edit:false,add:false,del:false,searchText:"Search",refreshText:"Clear Search"},
            {}, //edit
            {}, //add
            {}, //del
            {}, //search
            {} //view
        );
    }

    /**
     * Set up the jqGrid table and make the initial call to the server for data
     */
    var loadDistrictsTable = function() {
        $('.district_selection').live('change', setSelectedDistricts);
        _districtTable.jqGrid({
            pager:_options.districtPager,
            url:_options.districtUrl,
            hidegrid: false,
            /* scroll: true, /* dynamically scroll grid instead of using pager */
            gridview: true,
            altRows: true,
            altclass: 'chooserAlt',

            datatype: 'json',
            jsonReader: {
                repeatitems: false,
                id: 'pk'
            },
            colModel: [
                {name:'fields.name', label:'District Name'},
                {name:'fields.district_id', hidden: true},
                {name:'selected', label:' '}
            ],

            gridComplete: checkSelections,
            beforeRequest: appendExtraParamsToRequest,
            loadError: loadError,
            height: 'auto',
            autowidth: 'true',
            rowNum:15,
            sortname: 'id',
            viewrecords:true,
            mtype: 'POST',
            ajaxGridOptions: {
                beforeSend: function(xhr, settings) {
                    if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                        // Only send the token to relative URLs i.e. locally.
                        xhr.setRequestHeader("X-CSRFToken",
                                             $("#csrfmiddlewaretoken").val());
                    }
                }
            }
        }).jqGrid(
            'navGrid',
            '#' + _options.districtPager.attr('id'),
            {search:false,edit:false,add:false,del:false,searchText:"Search",refreshText:"Clear Search"},
            {}, //edit
            {}, //add
            {}, //del
            {}, //search
            {} //view
        );
    }

    var loadError = function(xhr, textStatus, error) {
        if (xhr.status == 403) {
            window.location.href = '/?msg=logoff';
        }
    }

    var planSelected = function(id) {
        // Set the internal variables for later use
        _selectedPlanId = id;
        loadDistrictsForPlan(id);
    };
    
    var setSelectedDistricts = function(checkbox) {
        var value = $(this).val();
        var selectionIndex = _selectedDistricts.indexOf(value);
        var checked = $(this).is(':checked');
        if (checked) {
            _selectedDistricts.push(value);
        } else if (!checked && selectionIndex > -1) {
            _selectedDistricts.splice(selectionIndex, 1);
        }
    };

    var checkSelections = function(grid) {
        var ids = _districtTable.jqGrid('getDataIDs');
        for (var i = 0; i < ids.length; i++) {
            var cl = ids[i];
            var selectionIndex = _selectedDistricts.indexOf(cl);
            var checked = selectionIndex > 1 ? ' checked ' : '';
            var content = '<input class="district_selection" type="checkbox" value="' + cl + '"' + checked + '/>'
            _districtTable.jqGrid('setRowData', cl, { selected: content });
        }
    }

    /**
     * When a plan is selected, load the districts in that plan
     * in the second grib
     */
    var loadDistrictsForPlan = function(id) {
        _selectedDistricts = [];
        var newUrl = _options.districtUrl.replace('PLAN_ID', id);
        _districtTable.setGridParam( {url:newUrl }).trigger('reloadGrid', [{page:1}]); 

    };

    var appendExtraParamsToRequest = function(xhr) {
        _planTable.setPostDataItem( 'owner_filter', 'all_available' );
        _planTable.setPostDataItem( 'legislative_body', $('#leg_selector').val() );
        /* TODO: implement search
        If the search box has a value, apply that to any filter
        var search = $('#plan_search');
        if (search.val() != '') {
                _planTable.setPostDataItem( '_search', true );
                _planTable.setPostDataItem( 'searchString', $('#plan_search').val() );
        } else {
                _planTable.setPostDataItem( '_search', false );
                _planTable.removePostDataItem( 'searchString' );
        } */
        _selectedPlanId = undefined;
        _selectedPlanName = undefined;
    };

    /**
     * Set up the search box feature
     */
    var setUpSearch = function() {
        // On enter key, search
        var searchBox = $('#plan_search');
        searchBox.keyup( function(event) {
            if (event.which == 13) {
                _planTable.jqGrid().trigger('reloadGrid');
            }
        });

        // watermark for non-html5 browsers
        if (document.getElementById('plan_search').getAttribute('placeholder') != 'Search') {
            searchBox.focus( function() {
                if ($(this).val() == 'Search') {
                    $(this).val('');
                    $(this).css('font', '');
                }
            });
            searchBox.blur( function() {
                if ($(this).val() == '') {
                    $(this).css('font', 'gray');
                    $(this).val('Search');
                }
            });

            // initial state showing watermark
            searchBox.css('font', 'gray');
            searchBox.val('Search');
        }
        
    };

    var initUI = function() {
        _options.submitButton.click( function() {
            _options.container.dialog('close');
            $('#working').dialog('open');
            // Send off our request
            $.ajax({
                url: _options.handlerUrl,
                type: 'POST',
                data: {
                    districts: _selectedDistricts,
                    version: $('#history_cursor').val()
                },
                success: function(data) {
                    $('#working').dialog('close');
                    if (data.success == true) {
                        PLAN_VERSION = data.version;
                        PLAN_HISTORY[PLAN_VERSION] = true;
                        $('#history_cursor').val(data.version);
                        // update the UI buttons to show that you can
                        // perform an undo now, but not a redo
                        $('#history_redo').addClass('disabled');
                        $('#history_undo').removeClass('disabled');

                        $('#copy_paste_tool').trigger('merge_success'); 
                    } else {
                        $('<div class="error" title="Sorry">Unable to paste districts:<p>' + data.message + '</p></div>').dialog({
                            modal: true,
                            autoOpen: true,
                            resizable: false
                        });
                    }
                }
            });
            // We don't want these districts selected anymore in the table
            _selectedDistricts = [];
            _districtTable.trigger('reloadGrid', [{page:1}]); 
        });
        $('#available_districts').bind('updated', function() {
            $('#shared_districts_column h2').text('2. Select ' + $('#available_districts').va() + ' districts to copy');
        });
    };

    //resize grid to fit window
    var resizeToFit = function() {
        // Shrink the container and allow for padding
        $('#table_container').width(parseInt($(window).width() - 550));
        var tblContainerWidth = parseInt($('#table_container').width());
        // if it's bigger than the minwidth, resize
        if (tblContainerWidth > 420) {
            _planTable.jqGrid('setGridWidth', tblContainerWidth + 15);
        }
    };
    
    $(window).resize( resizeToFit );

    return _self;
};

