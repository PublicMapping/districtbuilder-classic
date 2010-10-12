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
            }
        }, options),
        // bunch o variables
       
        _eventType,
        _nameRequired,
        _activeText,
        _copiedPlan;

    /**
     * Initialize the chooser. Setup the click event for the target to
     * show the chooser.
     *
     * Returns:
     *   The chooser.
     */
    _self.init = function() {
        _options.target.click(_self.show);

        _nameRequired = false;
        
        return _self;
    };

    /**
     * Show the chooser. This method makes an AJAX call to get the most
     * recent plans (templates, shared plans, etc) immediately prior to
     * showing the dialog.
     */
    _self.show = function() {
        _options.container.load('/districtmapping/plan/choose/',function(){
            setUpTarget(); 
            setUpEvents(); 
        
            $('#PlanChooser').dialog('open');
            loadButtons();
        });
    };

    /**
     * Setup and show the dialog. This function is called from within
     * the callback of the show's load function.
     */
    var setUpTarget = function() {
        if (!_options.closable) { 
            _options.closeOnEscape = false;
            _options.open = function(event, ui) {
                $(".ui-dialog-titlebar-close", $(this).parent()).hide();
            }

        }
        $('#PlanChooser').dialog(_options);
    };

    /**
     * Set up the events and configure the chooser for operation. This
     * function is called from within the callback of the show's load
     * function.
     */
    var setUpEvents = function() {
        $('.Selectors').hide();
        $('.SelectionGroup').hide();
        $('#SelectorHelp').show();
        $('#btnBlank').click(function() { 
            _eventType = 'blank'; 
            showOnly('#BlankSelection', '#btnBlank'); 
        });
        if ($('#ddlTemplate option').length == 0) {
            $('#btnTemplate').button('option', 'disabled', true);
            $('#btnTemplate').addClass('inactive');
        } else {
            $('#btnTemplate').click(function() { 
                _eventType = 'template'; 
                showOnly('#TemplateSelection','#btnTemplate'); 
            });
        }
        if ($('#ddlShared option').length == 0) {
            $('#btnShared').button('option', 'disabled', true);
            $('#btnShared').addClass('inactive');
        } else {
            $('#btnShared').click(function() { 
                _eventType = 'shared'; 
                showOnly('#SharedSelection','#btnShared'); 
            });
        }
        if ($('#ddlMine option').length == 0) {
            $('#btnMine').button('option', 'disabled', true);
            $('#btnMine').addClass('inactive');
        } else {
            $('#btnMine').click(function() { 
                _eventType = 'mine'; 
                showOnly('#MineSelection','#btnMine');
            });
        }
        $('#btnSelectPlan').click(selectPlan);
        $('#NewName').hide();
        $('input:radio').click( function() {
            if ($(this).val() == 'edit') {
                $('#NewName').hide(); 
                _nameRequired = false;
            } else {
                $('#NewName').show();
                _nameRequired = true;
            }
        });
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
        if (_eventType == 'blank' || _eventType == 'template' || (_eventType == 'shared' && !_options.anonymous) || 
            ( selectorId == '#MineSelection' && $('input:radio:checked').val() == 'saveas'  )) {
            $('#NewName').show();
            _nameRequired = true;
        } else {
            _nameRequired = false;
            $('#NewName').hide();
        }
    };

    /**
     * Select a plan. If a plan is a template, copy it and open that copy.
     * If a plan is shared, copy it and open that copy. If a plan is owned,
     * either open it for editing, or copy it to a new plan, then open it
     * for editing.
     */
    var selectPlan = function () {
        $('#btnSelectPlan').attr('disabled','true');
        _activeText = $('#btnSelectPlan span').text();
        $('#btnSelectPlan span').text('Please Wait...');
        var activeSelector = $('select.active');
        _copiedPlan = activeSelector.text();
        if (_nameRequired) {
            var name = $('#txtNewName').val();
            var url = '/districtmapping/plan/' + activeSelector.val() + '/copy/';
            if (_eventType == 'blank') {
                url = '/districtmapping/plan/create/';
            }

            if (name.trim().length == 0) { 
                alert ('A name for the copied template is required'); 
                $('#btnSelectPlan').attr('disabled',null);
                $('#btnSelectPlan span').text(_activeText);
                return; 
            }
            if (OpenLayers) {
                OpenLayers.Element.addClass(document.getElementById('btnSelectPlan'),'olCursorWait');
                OpenLayers.Element.addClass(document.body,'olCursorWait');
            }
            window.status = 'Please standby while creating new plan ...';
            $.post(url, { name: $('#txtNewName').val() }, copyCallback, 'json');
        }
        else if ( _eventType == 'mine' ) {
            window.location = '/districtmapping/plan/' + activeSelector.val() + '/edit/';
        }
        else {
            window.location = '/districtmapping/plan/' + activeSelector.val() + '/view/';
        }
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

            $('#btnSelectPlan').attr('disabled',null);
            $('#btnSelectPlan span').text(_activeText);

            if (OpenLayers) {
                OpenLayers.Element.removeClass(document.getElementById('btnSelectPlan'),'olCursorWait');
                OpenLayers.Element.removeClass(document.body,'olCursorWait');
            }
            return;
        }

        if (typeof(_gaq) != 'undefined' ) {
            if (_eventType == 'template' || _eventType == 'mine') {
                _gaq.push(['_trackEvent', 'Plans', 'Copied', _copiedPlan]);
            } else if (_eventType == 'blank') {
                _gaq.push(['_trackEvent', 'Plans', 'FromBlank']);
            }
        }

        data = data[0];
        if (data.pk) {
            window.location = '/districtmapping/plan/' + data.pk + '/edit/';
        } else {
            alert (data.message);
        }
    };

    return _self;
};

