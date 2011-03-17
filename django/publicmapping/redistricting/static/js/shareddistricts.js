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
            availableDistricts: -1,
            autoOpen: false,
            modal: true,
            width: 800,
            title: 'Copy and Paste Districts',
            resizable: false,
            closable: true
        }, options),

        // bunch o variables
        _map,
        _baseLayer,
        _districtLayer,
        _filterStrategy,
        _refreshStrategy,
        _disabledDialog,
        _planTable,
        _districtTable,
        _selectedPlanId,
        _selectedDistricts,
        _selectedPlanName,
        _available_districts

    /**
     * Initialize the chooser. Setup the click event for the target to
     * show the chooser.
     *
     * Returns:
     *   The chooser.
     */
    _self.init = function() {
        _options.container.dialog(_options);
        _options.target.click(showDialog);
        _selectedDistricts = [];
        _planTable = _options.planTable;
        loadPlanTable();
        _districtTable = options.districtTable;
        loadDistrictsTable();

        initUI();

        _available_districts = _options.availableDistricts;
        _options.target.trigger('available_districts_updated', [_available_districts]);
    };

    var showDialog = function() {
        _options.container.dialog('open');
        if (_map == undefined) {
            initMap();
        }
    };

    var showDisabledDialog = function() {
        _disabledDialog.dialog('open');
    };
    
    var closeDialog = function(event, ui) {
        _options.target.trigger('available_districts_updated', [_available_districts + _selectedDistricts.length]);
        _selectedDistricts = [];
        _selectedPlanId = undefined;
        _planTable.trigger('reloadGrid', [{page:1}]); 
        _districtTable.trigger('reloadGrid', [{page:1}]); 
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

            onSelectRow: setFilterForFeature,
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
            },
            beforeRequest: function () {
                // If we don't do this, the grid gets a 500 error the first time
                // before a plan is selected
                this.p.url = this.p.url.replace('PLAN_ID', 0);
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
        if (_selectedPlanId != id) {
            _selectedPlanId = id;
            _options.target.trigger('available_districts_updated', [_available_districts + _selectedDistricts.length]);
            _selectedDistricts = [];
            loadDistrictsForPlan(id);
            _districtLayer.protocol.url = '/districtmapping/plan/' + _selectedPlanId + '/district/versioned/';
            _refreshStrategy.refresh();
        }
    };
    
    var setSelectedDistricts = function(checkbox) {
        var value = $(this).val();
        var selectionIndex = _selectedDistricts.indexOf(value);
        var checked = $(this).is(':checked');
        if (checked) {
            _selectedDistricts.push(value);
            _options.target.trigger('available_districts_updated', [_available_districts -=1]);
        } else if (!checked && selectionIndex > -1) {
            _selectedDistricts.splice(selectionIndex, 1);
            _options.target.trigger('available_districts_updated', [_available_districts +=1]);
        }
    };

    var checkSelections = function(grid) {
        var ids = _districtTable.jqGrid('getDataIDs');
        for (var i = 0; i < ids.length; i++) {
            var cl = ids[i];
            var selectionIndex = _selectedDistricts.indexOf(cl);
            var checked = selectionIndex > -1 ? ' checked ' : '';
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
        _planTable.setPostDataItem( 'legislative_body', BODY_ID );
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
        // Create the dialog displayed when the tool is disabled
        _disabledDialog = $('<div id="copy_paste_disabled" title="Maximum Districts Reached">' + 
            'Your plan is at maximum capacity. Please delete a district to enable pasting.</div>')
            .dialog({ autoOpen: false, modal: true, resizable: false});

        // Use the closeDialog method to clear out the selections
        _options.container.bind('dialogclose', closeDialog);

        // Set up the message that displays how many districts are available for pasting
        _options.target.bind('available_districts_updated', function(event, new_value) {
            _available_districts = new_value;
            switch (_available_districts) {
                case 0:
                    var instructions = '2. Check your selections';
                    break;
                case 1:
                    var instructions = '2. Select a district to copy';
                    break;
                default:
                    if (_available_districts > 0) {
                        var instructions = '2. Select up to ' + _available_districts + ' districts to copy';
                    } else {
                        var instructions = '2. Remove ' + Math.abs(_available_districts) + ' before submitting';
                    }
            }

            $('#shared_districts_column h2').text(instructions);
        
            // The tool icon will be enabled or disabled 
            if (_available_districts == 0) {
                _options.target.unbind('click', showDialog);
                _options.target.bind('click', showDisabledDialog);
            } else {
                _options.target.unbind('click', showDisabledDialog);
                _options.target.bind('click', showDialog);
            }            
        });

        // Set up the submit button
        _options.submitButton.click( function() {
            if (_available_districts < 0) {
                return false;   
            }
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
                        $('<div class="error" title="Sorry">Unable to paste districts:<p>' + data.message + '</p></div>')
                            .dialog({modal:true, resizable:false});
                    }
                },
                error: function() {
                    $('<div class="error" title="Sorry">Unable to paste districts</div>')
                        .dialog({modal:true, resizable:false});
                }
            });
            _options.container.dialog('close');
            $('#working').dialog('open');
            // We don't want these districts selected anymore in the table
            _selectedDistricts = [];
            _districtTable.trigger('reloadGrid', [{page:1}]); 
        });

    };

    var initMap = function() {
        var width = 200;
        var size = STUDY_BOUNDS.getSize();
        var ratio = size.h / size.w;
        var height = width * ratio;

        var mapUrl = window.location.protocol + '//' + MAP_SERVER + '/geoserver/wms?request=GetMap&layers=LAYER&bbox=BBOX&Format=image/png&width=WIDTH&height=HEIGHT&srs=EPSG:3785';
        mapUrl = mapUrl.replace('LAYER', 'gmu:demo_county');
        mapUrl = mapUrl.replace('BBOX', STUDY_BOUNDS.toArray().join(','));
        mapUrl = mapUrl.replace('WIDTH', width);
        mapUrl = mapUrl.replace('HEIGHT', Math.ceil(height));
        var options = {
            // maxExtent: STUDY_BOUNDS,
            projection: "EPSG:3785",
            units:"m"
            //controls: [],
        };

        _baseLayer = new OpenLayers.Layer.Image(
            'Shared_Base',
            mapUrl,
            STUDY_BOUNDS,
            new OpenLayers.Size(height, width),
            {}
            // { numZoomLevels: 1 }
        );
        

        // Create  a vector layer with a feature ID filter strategy
        // On selection of a plan, get the districts in the plan
        // On clicking a district, set the feature filter to that featureID
        // The refresh the map
        
        _filterStrategy = new OpenLayers.Strategy.Filter({
            filter: new OpenLayers.Filter.FeatureId()
        });
        _refreshStrategy = new OpenLayers.Strategy.Refresh();

        _districtLayer = new OpenLayers.Layer.Vector(
        'District Layer', {
            protocol: new OpenLayers.Protocol.HTTP({
                url: '/districtmapping/plan/0/district/versioned/',
                format: new OpenLayers.Format.GeoJSON()
            }),
            strategies: [ _filterStrategy, _refreshStrategy ],
            style: new OpenLayers.Style({
                fill: true,
                fillColor: '#ee9900',
                strokeColor: '#ee9900',
                strokeWidth: 2
            }),
            projection: 'EPSG:3785'
        });

        _map = new OpenLayers.Map('shared_district_map_div', options);
        _map.addLayer(_baseLayer);
        _map.addLayer(_districtLayer);
        _map.zoomToExtent(STUDY_BOUNDS);
        
        _filterStrategy.activate();
        _refreshStrategy.activate();
    };


    var setFilterForFeature = function(districtId) {
        var filter = new OpenLayers.Filter.FeatureId({ fids: [ districtId ] });
        _filterStrategy.setFilter(filter);
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

