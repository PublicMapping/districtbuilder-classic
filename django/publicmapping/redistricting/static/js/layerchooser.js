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
       This script file defines behaviors of the 'Choose Layers' dialog
   
   Author: 
        Andrew Jennings, David Zwarg, Kenny Shepard
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * choosing map layers
 *
 * Parameters:
 *   options -- Configuration options for the layer chooser tool.
 */
layerchooser = function(options) {
    var _minWidth = 350;
    var _maxWidth = 790;

    var _self = {},
        _options = $.extend({
            container: {},
            target: {},
            legislativeButton: {},
            communityButton: {},
            okButton: {},
            referenceLayerContent: {},
            referenceLayerSelect: {},
            referencePlansTable: {},
            referencePlansPager: {},
            map: {},
            csrfmiddlewaretoken: {},
            referencePlansUrl: '',
            autoOpen: false,
            modal: false,
            width: _minWidth,
            height: 'auto',
            title: 'Choose Map Layers',
            resizable: false,
            closable: true
        }, options),

        _filterCommunities = false,
        _planTable,
        _districtTable;

    /**
     * Initialize the layer chooser tool. Setup the click event for the target to
     * show the layer chooser tool.
     *
     * Returns:
     *   The layer chooser tool.
     */
    _self.init = function() {
        _options.container.dialog(_options);
        _options.target.click(showDialog);
        _options.referenceLayerContent.hide();

        // Add button behavior
        var reload = function() {
            _planTable.trigger('reloadGrid', [{page:1}]);
            _options.referenceLayerContent.show();
            _options.container.dialog('option', 'width', _maxWidth);
            _options.container.dialog('option', 'position', 'center');
        };
        _options.legislativeButton.click(function(){
            _filterCommunities = false;
            reload();
        });
        _options.communityButton.click(function(){
            _filterCommunities = true;
            reload();
        });
        _options.okButton.click(function(){
            _options.container.dialog('close');
        });

        // Trigger event the selected reference layer has changed
        _options.referenceLayerSelect.change(function() {
            _options.map.trigger('reference_layer_changed', [_options.referenceLayerSelect.val()]);             
        });

        // Load Plan
        _planTable = _options.referencePlansTable;
        loadPlanTable();
    };

    /**
     * Set up the jqGrid table and make the initial call to the server for data
     */
    var loadPlanTable = function() {
        var planSelected = function(id) {
            var val = 'plan.' + id;
            _options.referenceLayerContent.hide();
            _options.referenceLayerSelect.append($('<option></option>').
                attr('value', val).
                text(_planTable.jqGrid('getRowData', id)['fields.name']));
                _options.container.dialog('option', 'width', _minWidth);
                _options.container.dialog('option', 'position', 'center');
            _options.referenceLayerSelect.val(val);
            _options.referenceLayerSelect.trigger('change');
        };
        
        var appendExtraParamsToRequest = function(xhr) {
            _planTable.setPostDataItem( 'owner_filter', 'all_available' );
            _planTable.setPostDataItem( 'is_community', _filterCommunities );
        };
    
        var loadError = function(xhr, textStatus, error) {
            if (xhr.status == 403) {
                window.location.href = '/?msg=logoff';
            }
        };
    
        _planTable.jqGrid({
            pager:_options.referencePlansPager,
            url:_options.referencePlansUrl,
            hidegrid: false,
            gridview: true,
            altRows: true,
            altclass: 'chooserAlt',
            datatype: 'json',
            jsonReader: {
                repeatitems: false,
                id: 'pk'
            },
            colModel: [
                {name:'fields.owner', label:'User Name', search:true, width: '110', fixed: true, sortable:true},
                {name:'fields.name', label:'Plan Name', search: true, sortable:true},
                {name:'fields.plan_type', label:'Plan Type', sortable:true, search:false}
            ],

            onSelectRow: planSelected,
            beforeRequest: appendExtraParamsToRequest,
            loadError: loadError,
            height: 'auto',
            autowidth: 'true',
            rowNum:10,
            sortname: 'id',
            viewrecords:true,
            mtype: 'POST',
            ajaxGridOptions: {
                beforeSend: function(xhr, settings) {
                    if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                        xhr.setRequestHeader("X-CSRFToken", _options.csrfmiddlewaretoken.val());
                    }
                }
             }
        }).jqGrid(
            'navGrid', '#' + _options.referencePlansPager.attr('id'),
            {search:false,edit:false,add:false,del:false,searchText:"Search",refreshText:"Clear Search"}
        );
    };

    /**
     * Display the dialog
     */
    var showDialog = function() {
        _options.container.dialog('open');
    };

    return _self;
};
