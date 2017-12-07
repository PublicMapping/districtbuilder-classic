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
            helpText: {},
            pager: {},
            dataUrl: ''
        }, options),
        // bunch o variables
       
        _table = null,
        _districtindexfilePublisher,
        _reaggregator,
        _selectedPlanId,
        _eventType = 'template',
        _nameRequired,
        _selectedPlanName,
        _editButton,
        _saveButton,
        _startText,
        _cancelButton;

    /**
     * Initialize the chooser. Setup the click event for the target to
     * show the chooser.
     *
     * Returns:
     *   The chooser.
     */
    _self.init = function() {
        _options.target.click(_self.show);
        _startText = _options.anonymous ? gettext("View Plan") : gettext("Start Drawing");
        _table = _options.table;
        _nameRequired = false;
        _reaggregator = reaggregator({ startText: _startText });
        _reaggregator.init();
        _options.helpText.hide();
        loadTable();
        resizeToFit();
        initButtons();
        setUpSearch();
        
        if (window.UPLOADED) {
            var div = $('<div />');
            var text = window.UPLOAD_STATUS ? gettext('Thanks! Your file has been uploaded, and your plan is being constructed. When your plan is completely constructed, you will receive an email from us.') : gettext('We\'re sorry! Your file was transferred to us, but there was a problem converting it into a plan. Make sure the file is a zipped block equivalency file, and please try again.');
            div.attr('title', gettext('Uploaded')).text(text).dialog({modal:true,resizable:false})
        }
        return _self;
    };

    /**
     * Show the edit button, the save/cancel buttons, or none
     */
    var editState = function(state) {
        if (state === 'view') {
            $('#plan_form #name').attr('disabled', 'disabled');
            $('#plan_form #description').attr('disabled', 'disabled');
            $('#start_mapping').removeAttr('disabled');
            _editButton.button('enable').show();
            _saveButton.button('disable').hide();
            _cancelButton.button('disable').hide();
        } else if (state === 'edit') {
            $('#plan_form #name').removeAttr('disabled');
            $('#plan_form #description').removeAttr('disabled');
            $('#start_mapping').attr('disabled', 'disabled');
            _editButton.button('disable').hide();
            _saveButton.button('enable').show();
            _cancelButton.button('enable').show();
        } else {
            $('#plan_form #name').attr('disabled', 'disabled');
            $('#plan_form #description').attr('disabled', 'disabled');
            $('#start_mapping').removeAttr('disabled');
            _editButton.button('disable').hide();
            _saveButton.button('disable').hide();
            _cancelButton.button('disable').hide();
        }
    }

    /**
     * Select a plan. If a plan is a template, copy it and open that copy.
     * If a plan is shared, copy it and open that copy. If a plan is owned,
     * either open it for editing, or copy it to a new plan, then open it
     * for editing.
     */
    var selectPlan = function () {
        // Notify the reaggregator of reaggregation button clicks
        if (DB.util.startsWith($('#start_mapping .ui-button-text').html(), 'Reaggregate')) {
            _reaggregator.reaggregateClicked(_selectedPlanId);
            return;
        }
        
        // If we're anonymous, just view the selected map
        if (_options.anonymous) {
            if (typeof(_selectedPlanId) == 'undefined') {
                alert(gettext('Choose a plan from the table first'));
                return false;
            }
            window.location = '/districtmapping/plan/' + _selectedPlanId + '/view/';
            return false;
        }

        // If the user is using a template, they should have clicked the table first
        if (typeof(_selectedPlanId) == 'undefined' && 'blank|upload'.indexOf(_eventType) == -1 ) {
            alert(gettext('Choose a plan from the table first'));
            return false;
        }

        // If a name for a new plan is required, be certain it exists
        if (_nameRequired) {
            var name = $('#txtNewName').val();
            if (name.trim().length == 0) { 
                alert (gettext('A name for the copied template is required')); 
                return false; 
            }

            var url = '/districtmapping/plan/' + _selectedPlanId + '/copy/';
            if (_eventType == 'blank') {
                url = '/districtmapping/plan/create/';
            }

            if (_eventType == 'upload') {
                var email = $('#userEmail').val();
                if (email.trim() == '' || !email.match(/^([\w\-\.\+])+\@([\w\-\.])+\.([A-Za-z]{2,4})$/)) {
                    alert(gettext('Please provide a valid email address.'));
                    return false;
                }
                if ($('#indexFile').val() == '') {
                    alert(gettext('Please provide a zipped district index file.'));
                    return false;
                } 
                if ($('#leg_selector_upload').val() == '') {
                    alert(gettext('You must select a legislative body from the dropdown in the upload form'));
                    return false;
                }
                // Get the form for uploading.  Be sure not to move the input:file element
                // out of the form - you can't clone it in javascript.
                var form = $('#frmUpload');
                $('#txtNewName').clone().appendTo(form).hide();
                
                form.submit();
                return false;
            }
            else {
                $('#start_mapping').attr('disabled', 'disabled');                
                $('#start_mapping .ui-button-text').html(gettext('Creating New Plan...'));
                window.status = gettext('Please standby while creating new plan ...');
                $.ajax({
                    url:url, 
                    data:{ 
                        name: $('#txtNewName').val(),
                        legislativeBody: $('#leg_selector').val()
                    },
                    dataType:'json',
                    success: copyCallback,
                    error: function(xhr,textStatus,message){
                        var contentType = xhr.getResponseHeader('Content-Type');
                        // if the content is text/html, redirect to '/',
                        // since we probably just got logged out from 
                        // another session
                        if (DB.util.startsWith(contentType, 'text/html')) {
                            window.location.href='/?msg=logoff';
                        }
                    },
                    type: 'POST'
                });
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
            if ('redirect' in data) {
                window.location.href = data.redirect;
                return;
            }

            var div = $('<div />').attr('title', gettext('Creation Error'));
            div.append('<p />').text(data.message);
            var tip = $('<div />');
            tip.append($('<b />').text(gettext('Tip: ')));
            tip.append($('<span />').text(gettext('Make sure the new plan\'s name is unique.')));
            div.append(tip).dialog({
                modal:true,
                resizable:false,
                close: function(event, ui){
                    $('#start_mapping').attr('disabled', null);
                    $('#start_mapping .ui-button-text').html(_options.anonymous ? gettext("View Plan") : gettext("Start Drawing"));
                }
            });

            if (OpenLayers) {
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

    // Formatters for the jqGrid plugin used in the plan chooser table
    
    // Formatter used to display images in the shared column of the jqGrid
    $.extend($.fn.fmatter, {
        sharedImageFormatter: function (shared) {
            return "<img height='16' width='16' src='/static/images/icon-" + ((shared) ? "" : "un") + "shared.png' />";
        }, 

        // Formatter used for dates. The server returns a UTC timestamp
        // This formatter shifts the timestamp to local time if neccesary
        tzAwareDateFormatter: function(cellvalue, options, rowdata) {
            var newDate = new Date(cellvalue * 1000);
            if ($.browser.mozilla) {
                 // get the time zone offset in minutes, then multiply to get
                 // milliseconds
                 var offset = newDate.getTimezoneOffset() * 60000;
                 newDate = new Date(newDate - offset);
            }
            return newDate;
            // return $.fn.fmatter.date(newDate.valueOf(), options, rowdata, 'show');
        },

        // Formatter used to display the "trash can" image in the delete
        // column.
        deleteFormatter: function (a, b, obj) {
            var id = "delete-" + obj.pk;
            return "<img id='" + id  + "' class='delclick' height='16'" + 
                "width='16' src='/static/images/icon-trash.png' alt='" +
                obj.fields.name + "' />";
        },

        // Formatter and state objects used for coloring reaggregating plans
        rowColorFormatterState: [],
        rowColorFormatter: function(cellValue, options, rowObject) {
            if (cellValue === gettext("Needs reaggregation")) {
                $.fn.fmatter.rowColorFormatterState
                    .push({ id: options.rowId, color: "#DD4444" }); // red
            } else if (cellValue === gettext("Reaggregating")) {
                $.fn.fmatter.rowColorFormatterState
                    .push({ id: options.rowId, color: "#FF9933" }); // orange
            }
            return cellValue;
        }
    });


    /**
     * Set up the jqGrid table and make the initial call to the server for data
     */
    var loadTable = function() {
        _table.jqGrid({
            pager:_options.pager,
            url:_options.dataUrl,
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
                {name:'fields.name', label:gettext('Plan Name'), search: true, sortable:true},
                {name:'fields.owner', label:gettext('Author'), search:true, width: '110', fixed: true, sortable:true},
                {name:'fields.description', label:gettext('Description'), hidden:true, search:true},
                {name:'fields.is_shared', label:gettext('Shared'), sortable:true, search:false, width:'60', fixed: true, align: 'center', formatter:'sharedImageFormatter'},
                {name:'fields.edited', label:gettext('Last Edited'), sortable:true, search:false, width:'130', fixed: true, align: 'center', formatter:'tzAwareDateFormatter', formatoptions: { srcformat: 'UniversalSortableDateTime', newformat: get_format('SHORT_DATE_FORMAT') + ' g:i A'}},
                {name:'fields.delete', label:gettext('Delete'), formatter: 'deleteFormatter', width:'60', fixed: true, align:'center'},
                {name:'fields.can_edit', label:gettext('Edit'), search:false, hidden: true},
                {name:'fields.districtCount', label:gettext('# Districts'), search:false, sortable:true, hidden:true},
                {name:'fields.processing_state', label:gettext('State'), search:false, sortable:false, hidden:true, formatter:'rowColorFormatter'}
            ],

            onSelectRow: rowSelected,
            beforeRequest: appendExtraParamsToRequest,
            loadError: loadError,
            height: 'auto',
            autowidth: 'true',
            rowNum:15,
            sortname: 'fields.edited',
            sortorder: 'desc',
            viewrecords:true,
            mtype: 'POST',
            loadBeforeSend: function(xhr) {
                if (!(/^http:.*/.test(this.p.url) || /^https:.*/.test(this.p.url))) {
                    // Only send the token to relative URLs i.e. locally.
                    xhr.setRequestHeader("X-CSRFToken",
                                         $("input[name=csrfmiddlewaretoken]").val());
                }
            },
            loadComplete: function(data) {
                // Notify the reaggregator of the new data
                _reaggregator.dataUpdated(data);
            },
            gridComplete: function(a, b, c) {
                // Color row background based on processing_state
                $.each($.fn.fmatter.rowColorFormatterState, function(ind, row) {
                    $("#" + row.id).find("td").css("background-color", row.color);
                });
                $.fn.fmatter.rowColorFormatterState = [];
                    
                // Add functionality to the delete plan buttons
                $('.delclick').click(function(obj) {
                    var id = obj.target.id.substring('delete-'.length);
                    var name = obj.target.alt;
                    
                    $('<div />').text(gettext('Really delete plan: ') + name + '?').dialog({
                        modal: true,
                        autoOpen: true,
                        title: gettext('Delete Plan'),
                        buttons: [{ 
                            text: gettext('Yes'),
                            click: function() {
                                $(this).dialog('close');
                                var waitDialog = $('<div />').text(
                                        gettext('Please wait. Deleting plan.')).dialog({
                                    modal: true, autoOpen: true, title: gettext('Deleting Plan'),
                                    escapeOnClose: false, resizable:false,
                                    open: function() { $(".ui-dialog-titlebar-close", $(this).parent()).hide(); }
                                });

                                $.ajax({
                                    type: 'POST',
                                    url: '/districtmapping/plan/' + id + '/delete/',
                                    success: function(data) {
                                        waitDialog.remove();
                                        if (data.success) {
                                            _table.jqGrid().trigger('reloadGrid', [{ page:1 }]);
                                        } else if ('redirect' in data) {
                                            window.location.href = data.redirect;
                                        } else if ('message' in data) {
                                            $('<div />').attr('title', gettext('Error Deleting Plan'))
                                                .text(data.message).dialog({modal:true, resizable:false});
                                        }
                                    },
                                    error: function(xhr, textStatus, message) {
                                        waitDialog.remove();
                                        if (xhr.status == 403) {
                                            window.location.href = '/?msg=logoff';
                                        } else {
                                            $('<div />').attr('title', gettext('Error Deleting Plan'))
                                                .text(gettext('Please try again later.'))
                                                .dialog({modal:true, resizable:false});
                                        }
                                }});}
                        }, {
                             text: gettext('No'),
                             click: function() { $(this).dialog('close'); }
                        }]
                    });
                });
            }
        }).jqGrid(
            'navGrid',
            '#' + _options.pager.attr('id'),
            {search:false,edit:false,add:false,del:false,searchText:gettext("Search"),refreshText:gettext("Clear Search")},
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

    var rowSelected = function(id) {
        // Don't do anything if the selected plan hasn't changed
        if (_selectedPlanId === id) {
            _reaggregator.planSelected(id);            
            return;
        }
        
        // Set the internal variables for later use
        _selectedPlanId = id;
        _selectedPlanName = _table.jqGrid('getCell', id, 'fields.name');
        var can_edit = _table.jqGrid('getCell', id, 'fields.can_edit');
        _table.jqGrid('GridToForm', id, '#plan_form'); 

        $('#districtCount').val('...  ');
        var progress = setInterval(function(){
            var val = $('#districtCount').val();
            $('#districtCount').val( val.substr(4) + val.substr(0,4) );
        }, 125);

        $.ajax({
            type:'GET',
            dataType: 'json',
            url: '/districtmapping/plan/' + _selectedPlanId + '/districts/',
            success: function(data) {
                var dcount = 0;
                for (var didx = 0; didx < data.districts.length; didx++) {
                    if (data.districts[didx].id != 0) {
                        dcount++;
                    }
                }
                clearInterval(progress);
                $('#districtCount').val(dcount);
            },
            error: function() {
                clearInterval(progress);
                $('#districtCount').val('n/a');
            }
        });

        // workaround for problem with jqGrid custom formatter with boolean (is_shared)
        var shared = $('#is_shared');
        if (DB.util.contains(shared.val(), "unshared")) {
            shared.val(gettext('No'));
        } else {
            shared.val(gettext('Yes'));
        }

        if (can_edit == "true") {
            editState('view');
            // clear previous handlers
            _saveButton.unbind();
            // On save click, submit new plan attribute data to server
            _saveButton.click( function() {
                $.ajax({
                    type: 'POST',
                    dataType: 'json',
                    url: '/districtmapping/plan/' + _selectedPlanId + '/attributes/',
                    data: {
                        name: $('#plan_form #name').val(),
                        description: $('#plan_form #description').val()
                    }, 
                    success: function(data) {
                        if (data.success) {
                            _table.jqGrid('FormToGrid', _selectedPlanId, '#plan_form');
                            editState('view');
                        }
                        else if ('redirect' in data) {
                            window.location.href = data.redirect;
                        }
                        else if ('message' in data) {
                            $('<div />').attr('title', gettext('Error Saving Details'))
                                .text(data.message).dialog({modal:true, resizable:false});
                        }
                    },
                    error: function(xhr, textStatus, message) {
                        if (xhr.status == 403) {
                            window.location.href = '/?msg=logoff';
                        }
                    }
                });
                return false;
            });
        } else {
            editState('none');
        }

        // Update the district index file publisher
        if (_districtindexfilePublisher) {
            _districtindexfilePublisher.setUpdateVisibility(false);
        }

        var row = $(_table.getInd(id, true));
        var difile = row.data('difile');
        if (difile == null) {
            difileIndex = districtfile({
                target: $('#chooserFileDownloadTargetIndex'),
                planId: id,
                type: 'index',
                display: 'Index File'
            });
            difileShape = districtfile({
                target: $('#chooserFileDownloadTargetShape'),
                planId: id,
                type: 'shape',
                display: 'Shapefile'
            });
            row.data('difileIndex', difileIndex);
            row.data('difileShape', difileShape);
        }
        difileIndex.setUpdateVisibility(true).init();
        _districtindexfilePublisher = difileIndex;
        difileShape.setUpdateVisibility(true).init();
        _districtindexfilePublisher = difileShape;
        // Reset the button to starting text and enabled state
        $('#start_mapping .ui-button-text').html(_startText);
        $('#start_mapping').attr('disabled', false);

        // Notify reaggregator of the new plan
        _reaggregator.planSelected(id);
    };
    
    var appendExtraParamsToRequest = function(xhr) {
        _table.setPostDataItem( 'owner_filter', _eventType );
        _table.setPostDataItem( 'legislative_body', $('#leg_selector').val() );
        /* If the search box has a value, apply that to any filter */
        var search = $('#plan_search');
        if (search.val() != '' && search.val() != gettext('Search')) {
                _table.setPostDataItem( '_search', true );
                _table.setPostDataItem( 'searchString', $('#plan_search').val() );
        } else {
                _table.setPostDataItem( '_search', false );
                _table.removePostDataItem( 'searchString' );
        }
    };

    /**
     * Set up the search box feature
     */
    var setUpSearch = function() {
        // On enter key, search
        var searchBox = $('#plan_search');
        searchBox.keyup( function(event) {
            if (event.which == 13) {
                var search_filter = $.trim($('#plan_search').val());
                if (search_filter !== '') {
                    $('#search_filter').text(gettext('Current Filter: ') + search_filter);
                } else {
                    $('#search_filter').text('');
                }
                clearPlanForm();
                _table.jqGrid().trigger('reloadGrid', [{ page:1 }]);
            }
        });

        // watermark for non-html5 browsers
        if (document.getElementById('plan_search').getAttribute('placeholder') != gettext('Search') ||
                navigator.userAgent.indexOf('Firefox/3') > -1) {
            searchBox.focus( function() {
                if ($(this).val() == gettext('Search')) {
                    $(this).val('');
                    $(this).css('color', '#000000');
                }
            });
            searchBox.blur( function() {
                if ($(this).val() == '') {
                    $(this).css('color', '#666666');
                    $(this).val(gettext('Search'));
                }
            });

            // initial state showing watermark
            searchBox.css('font', 'gray');
            searchBox.val(gettext('Search'));
        }
        
    };

    var showItems = function (input, radio, table, sharedCol, ownerCol) {
        $('#newName').toggle(input);
        $('#radCopyOrEdit').toggle(radio);
        $('#table_container').toggle(table);

        editState('none');

        if (sharedCol) {
            _options.table.jqGrid('showCol', 'fields.is_shared');
            _options.table.jqGrid('showCol', 'fields.delete');
        } else {
            _options.table.jqGrid('hideCol', 'fields.is_shared');
            _options.table.jqGrid('hideCol', 'fields.delete');
        }
        if (ownerCol) {
            _options.table.jqGrid('showCol', 'fields.owner');
        } else {
            _options.table.jqGrid('hideCol', 'fields.owner');
        }
        // There's a bug in hiding/showing columns. Tables get a pixel smaller each time
        resizeToFit();

        $('#upload_selection').toggle(_eventType == 'upload'); 
    };

    var setActiveTab = function($currTab) {
        $('#plan_buttons li').each(function() {
          $(this).removeClass('active');
        });
        $currTab.addClass('active');

        // Notify the reaggregator of the new filter
        _reaggregator.filterChanged($currTab.attr('id'));
    };
    
    var initButtons = function() {
        // Save these for later        
        _editButton = $('#edit_plan_attr');
        _saveButton = $('#save_plan_attr');
        _cancelButton = $('#cancel_edit_plan_attr');

        // Set up the cancel button when editing;
        _editButton.click( function() {
            editState('edit');
            return false;
        });
        _cancelButton.button().click( function() {
            _table.jqGrid('GridToForm', _selectedPlanId, '#plan_form'); 
            var shared = $('#is_shared');
            if (DB.util.contains(shared.val(), "unshared")) {
                shared.val(gettext('No'));
            } else {
                shared.val(gettext('Yes'));
            }
            editState('view');
            return false;
        });

        $('#leg_selector').change( function() {
            _table.jqGrid().trigger('reloadGrid', [{ page:1 }]);
        });

        // Set up the filter buttons
        $('#filter_templates').click( function () {
            _eventType = 'template';
            _nameRequired = true;
            _table.jqGrid().trigger('reloadGrid', [{ page:1 }]);
            if (_options.anonymous) {
                showItems(false, false, true, false, true);
            } else {
                showItems(true, false, true, false, true);
            }
            $('#start_mapping .ui-button-text').html(_startText);
            $('#start_mapping').attr('disabled', 'disabled');
            setActiveTab($(this));
           
        });        
        $('#filter_shared').click( function () {
            _eventType = 'shared';
            _nameRequired = true;
            _table.jqGrid().trigger('reloadGrid', [{ page:1 }]);
            if (_options.anonymous) {
                showItems(false, false, true, false, true);
            } else {
                showItems(true, false, true, false, true);
            }
            $('#start_mapping .ui-button-text').html(_startText);
            $('#start_mapping').attr('disabled', 'disabled');
            setActiveTab($(this));
        });        
        $('#filter_mine').click( function () {
            _eventType = 'mine';
            _nameRequired = false;
            _table.jqGrid().trigger('reloadGrid', [{ page:1 }]);
            $('input:radio[name=Edit]').filter('[value=edit]').prop('checked', true);
            showItems(false, true, true, true, false);
            $('#start_mapping .ui-button-text').html(_startText);
            $('#start_mapping').attr('disabled', 'disabled');
            setActiveTab($(this));            
        });        
        $('#new_from_file').click( function() {
            _eventType = 'upload';
            _nameRequired = true;
            showItems(true, false, false, false, true);
            $('#start_mapping .ui-button-text').html(gettext('Upload Plan'));
            $('#start_mapping').attr('disabled', false);            
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
    
        // When switching tabs, clear the details form
        $('#plan_buttons li').click( clearPlanForm );

        // If anonymous, hide the "new plan" options
        if (_options.anonymous) {
            $('#filter_mine').hide();
            $('#new_from_blank').hide();
            $('#new_from_file').hide();
            $('#lblStartDrawing').hide();
            var anonText = gettext('Click the button to view the map as a guest');
            if ($('#leg_selector option').length > 1) {
                anonText = '4. ' + anonText;
            } else {
                anonText = '3. ' + anonText;
            }
            $('#start_mapping').before($('<div />').text(anonText));
        }

        // set the start mapping button to select the plan
        $('#start_mapping').click(selectPlan);

        // Start the chooser with templates
        $('#filter_templates').click();
    };

    var clearPlanForm = function() {
        $('#plan_form *[type=text]').val('');
        if (_districtindexfilePublisher) {
            _districtindexfilePublisher.setUpdateVisibility(false);
        }    
        $('#chooserFileDownloadTarget').empty();
    };

    //resize grid to fit window
    var resizeToFit = function() {
        if (_table === null) return;
        // Shrink the container and allow for padding
        $('#table_container').width(parseInt($(window).width() - 550));
        var tblContainerWidth = parseInt($('#table_container').width());
        // if it's bigger than the minwidth, resize
        if (tblContainerWidth > 420) {
            _table.jqGrid('setGridWidth', tblContainerWidth + 15);
        }
    };
    
        $(window).resize( resizeToFit );

    return _self;
};

