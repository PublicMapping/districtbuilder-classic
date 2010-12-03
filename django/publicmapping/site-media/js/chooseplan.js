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
       This script file defines behaviors of the 'Choose Plan' dialog.
   
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
chooseplan = function(options) {

    var _self = {},
        _options = $.extend({
            target: {},
            container: {},
            autoOpen: false,
            modal: true,
            width: 600,
            resizable: false,
            closable: true,
            close: function(event, ui) {
                $('#PlanChooser').dialog('destroy').detach();
            },
            table: {},
            pager: {},
            dataUrl: ''
        }, options),
        // bunch o variables
       
        _table,
        _selectedPlanId,
        _eventType = 'template',
        _nameRequired,
        _activeText,
        _selectedPlanName,
        _copyOrCreate;

    /**
     * Initialize the chooser. Setup the click event for the target to
     * show the chooser.
     *
     * Returns:
     *   The chooser.
     */
    _self.init = function() {
        _options.target.click(_self.show);

        _table = _options.table;
        _nameRequired = false;
        loadTable();
        initButtons();
        
        if (window.UPLOADED) {
            var text = window.UPLOAD_STATUS ? 'Thanks! Your file has been uploaded, and your plan is being constructed. When your plan is completely constructed, you will receive an email from us.' : 'We\'re sorry! Your file was transferred to us, but there was a problem converting it into a plan. Make sure the file is a zipped block equivalency file, and please try again.';
            $('<div title="Uploaded">' + text + '</div>').dialog({modal:true})
        }
        return _self;
    };

    /**
     * Show one choosing mode. This function is called from within the
     * setUpEvents function.
     *
     * Parameters:
     *   selectorId -- The selector of the panel body.
     *   buttonID -- The selector of the button that corresponds to this
     *               panel.
     */
    var showOnly = function(selectorId,buttonID) {
        $('#TemplateTypeButtons li').removeClass('active');
        $(buttonID).addClass('active');
        
        $('#SelectorsHelp').hide();
        $('.SelectionGroup').hide();
        $('.Selectors').removeClass('active');
        $(selectorId).show();
        var selectors = $(selectorId + ' .Selectors'); 
        selectors.show().addClass('active');
        if ( selectors.length > 0 && selectors[0].nodeName != 'SELECT' ) {
            $('#btnSelectPlan').hide();
        }
        else {
            $('#btnSelectPlan').show();
        }
        if (_eventType == 'blank' || _eventType == 'template' || _eventType == 'upload' || (_eventType == 'shared' && !_options.anonymous) || 
            ( selectorId == '#MineSelection' && $('input:radio:checked').val() == 'saveas'  )) {
            $('#NewName').show();
            _nameRequired = true;
        } else {
            _nameRequired = false;
            $('#NewName').hide();
        }
        if (_eventType == 'table') {
            loadTable();
        }
    };

    /**
     * Select a plan. If a plan is a template, copy it and open that copy.
     * If a plan is shared, copy it and open that copy. If a plan is owned,
     * either open it for editing, or copy it to a new plan, then open it
     * for editing.
     */
    var selectPlan = function () {
        // If the user is using a template, they should have clicked the table first
        if (typeof(_selectedPlanId) == 'undefined' && 'blankupload'.indexOf(_eventType) == -1 ) {
            alert('Choose a plan from the table first');
            return false;
        }

        // If a name for a new plan is required, be certain it exists
        if (_nameRequired) {
            var name = $('#txtNewName').val();
            if (name.trim().length == 0) { 
                alert ('A name for the copied template is required'); 
                return false; 
            }

            var url = '/districtmapping/plan/' + _selectedPlanId + '/copy/';
            if (_eventType == 'blank') {
                url = '/districtmapping/plan/create/';
            }

            if (_eventType == 'upload') {
                var email = $('#userEmail').val();
                if (email.trim() != '') {
                    if (!(email.match(/^([\w\-\.\+])+\@([\w\-\.])+\.([A-Za-z]{2,4})$/))) 
                    {
                        alert('Please provide a valid email address.');
                        $('#btnSelectPlan').attr('disabled',null);
                        $('#btnSelectPlan span').text(_activeText);
                        return false;
                    }
                }
            }
            if (_eventType == 'upload') {
                // Get the form for uploading.  Be sure not to move the input:file element
                // out of the form - you can't clone it in javascript.
                var $form = $('#frmUpload');
                $('#txtNewName').clone().appendTo($form);
                $('#leg_selector').clone().attr('name', 'legislativeBody').appendTo($form);
                $form.submit();
                return false;
            }
            else {
                window.status = 'Please standby while creating new plan ...';
                $.post(
                    url, 
                    { 
                        name: $('#txtNewName').val(),
                        legislativeBody: $('#leg_selector').val()
                    }, 
                    copyCallback, 
                    'json');
                return false;
            }
        }
        else if ( _eventType == 'mine' ) {
            window.location = '/districtmapping/plan/' + _selectedPlanId + '/edit/';
        }
        else {
            window.location = '/districtmapping/plan/' + _selectedPlanId + '/view/';
        }

        return false;
    };

    /**
     * A callback that redirects to the new copy of a plan, or displays an error message.
     *
     * Parameters:
     *   data -- The JSON data object returned by the server.
     */
    var copyCallback = function(data) {
        if ('success' in data && !data.success) {
            alert( data.message + '\n\nTip: Make sure the new plan\'s name is unique.' );

            if (OpenLayers) {
                OpenLayers.Element.removeClass(document.getElementById('btnSelectPlan'),'olCursorWait');
                OpenLayers.Element.removeClass(document.body,'olCursorWait');
            }
            return;
        }

        if (typeof(_gaq) != 'undefined' ) {
            if (_eventType == 'template' || _eventType == 'mine') {
                _gaq.push(['_trackEvent', 'Plans', 'Copied', _selectedPlanName]);
            } else if (_eventType == 'blank') {
                _gaq.push(['_trackEvent', 'Plans', 'FromBlank']);
            } else if (_eventType == 'upload') {
                _gaq.push(['_trackEvent', 'Plans', 'Uploaded']);
            }
        }

        data = data[0];
        if (data.pk) {
            window.location = '/districtmapping/plan/' + data.pk + '/edit/';
        } else {
            alert (data.message);
        }
    };

    /**
     * Set up the jqGrid table and make the initial call to the server for data
     */
    var loadTable = function() {
        _table.jqGrid({
            pager:_options.pager,
            url:_options.dataUrl,
            caption: 'All Plans',
            hidegrid: false,
            /* scroll: true, /* dynamically scroll grid instead of using pager */
            gridview: true,
            altRows: true,

            datatype: 'json',
            jsonReader: {
                repeatitems: false,
                id: 'pk',
            },
            colModel: [
                {name:'fields.name', label:'Name', search:true, sortable:true, editable:true},
                {name:'fields.description', label:'Description', hidden:true, search:true, editable:true},
                {name:'fields.owner', label:'Author', search:true, sortable:true},
                {name:'fields.edited', label:'Last Edited', search:true, sortable:true, datefmt:'MM/DD/Y'},
                {name:'fields.is_shared', label:'Shared', search:true, sortable:true, formatter:'checkbox', width:'60'},
                {name:'fields.districtCount', label:'# Districts', sortable:true, hidden:true},
            ],

            onSelectRow: rowSelected,
            beforeRequest: appendExtraParamsToRequest,
            height: 'auto',
            autowidth: true,
            rowNum:10,
            rowList:[10,20,30],
            sortname: 'id',
            viewrecords:true,
            mtype: 'POST'
        }).jqGrid(
            'navGrid',
            '#' + _options.pager.attr('id'),
            {search:true,edit:true,add:false,del:false,searchText:"Search",refreshText:"Clear Search"},
            {}, //edit
            {}, //add
            {}, //del
            {sopt: ['cn', 'ge', 'le'], closeAfterSearch: true, closeOnEscape: true }, // search
            {} //view
        );
    }

    var rowSelected = function(id) {
        // Set the internal variables for later use
        _selectedPlanId = id;
        _selectedPlanName = _table.jqGrid('getCell', id, 'fields.name');
        // Update the data editing form
        _table.jqGrid('GridToForm', id, '#plan_form');
    };
    
    var appendExtraParamsToRequest = function(xhr) {
        _table.setPostDataItem( 'owner_filter', _eventType );
        _table.setPostDataItem( 'legislative_body', $('#leg_selector').val() );
        _selectedPlanId = undefined;
        _selectedPlanName = undefined;
    };

    var showItems = function (input, radio, table, sharedCol, ownerCol) {
        $('#newName').toggle(input);
        $('#radCopyOrEdit').toggle(radio);
        $('#table_container').toggle(table);

        if (sharedCol) {
            _options.table.jqGrid('showCol', 'fields.is_shared');
        } else {
            _options.table.jqGrid('hideCol', 'fields.is_shared');
        }
        if (ownerCol) {
            _options.table.jqGrid('showCol', 'fields.owner');
        } else {
            _options.table.jqGrid('hideCol', 'fields.owner');
        }
        $('#upload_selection').toggle(_eventType == 'upload'); 
    };

    var setActiveTab = function($currTab) {
        $('#plan_buttons li').each(function() {
          $(this).removeClass('active');
        });
        $currTab.addClass('active');
     };
    
    var initButtons = function() {
    
        $('#filter_templates').click( function () {
            _eventType = 'template';
            _nameRequired = true;
            _table.jqGrid().trigger('reloadGrid').setCaption('Templates');
            showItems(true, false, true, false, true);
            $('#edit_plan').hide()
            setActiveTab($(this));
           
        });        
        $('#filter_shared').click( function () {
            _eventType = 'shared';
            _nameRequired = true;
            _table.jqGrid().trigger('reloadGrid').setCaption('Shared Plans');
            showItems(true, false, true, false, true);
            $('#edit_plan').hide()
            setActiveTab($(this));
        });        
        $('#filter_mine').click( function () {
            _eventType = 'mine';
            _nameRequired = true;
            _table.jqGrid().trigger('reloadGrid').setCaption('My Plans');
            $('input:radio[name=Edit]').filter('[value=edit]').attr('checked', true);
            _nameRequired = false;
            showItems(false, true, true, true, false);
             $('#edit_plan').show()
            setActiveTab($(this));            
        });        
        $('#new_from_blank').click( function() {
            _eventType = 'blank';
            showItems(true, false, false, false, true);
             setActiveTab($(this));           
        });
        $('#new_from_file').click( function() {
            _eventType = 'upload';
            showItems(true, false, false, false, true);
            setActiveTab($(this));           
        });

        $('#edit_plan').button().click( function() {
            ('#plan_form #name').removeAttr('disabled');
             setActiveTab($(this));           
        });
        
        $('#radCopyOrEdit input:radio').change( function() {
            if ($(this).val() == 'edit') {
                $('#newName').hide(); 
                _nameRequired = false;
            } else {
                $('#newName').show();
                _nameRequired = true;
            }
        });
        $('#filter_templates').click();

        $('#start_mapping').click(selectPlan);
    };


    return _self;
};

