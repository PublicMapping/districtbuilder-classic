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
       This script file defines the behaviors for generating reports of
       Plans.

   Author:
        Andrew Jennings, David Zwarg
*/

/**
 * Create a jQuery compatible object that contains functionality for
 * generating plan reports.
 *
 * Parameters:
 *   options -- Configuration options for the dialog.
 */
reports = function(options) {

    var _self = {},
        _options = $.extend({
            previewContainer: $('#reportPreview'),
            trigger: $('#btnPreviewReport'),
            planId: 0,
            calculatorReports: [],
            callback: function() {}
        }, options),
        _popVar,
        _popVarExtra,
        _ratioVars,
        _splitVars,
        _blockLabelVar,
        _repCompactness,
        _repCompactnessExtra,
        _repSpatial,
        _repSpatialExtra;

    /**
     * Initialize the reporting interface.
     *
     * Returns:
     *   The reporting interface.
     */
    _self.init = function() {
        _options.trigger.click( function() {
            submitReportRequestToServer();
            _options.callback();
        });

        if (_options.calculatorReports.length > 0) {
            createCalculatorCheckboxes();
        }
        return _self;
    };

    var pollCount = 0;

    /**
     * Create all of the checkboxes/label for calculator reports.
     * This is only called when calculator reports are enabled.
     */
    var createCalculatorCheckboxes = function() {
        // master
        $(_options.calculatorReports).each(function(i, group) {
            // option1 and option2 are the left and right divs
            var optionsId = 'options' + ((i % 2 === 0) + 1);
            if ($('#' + optionsId).length === 0) {
                $('#options').append($("<div />").prop('id', optionsId));
            }

            var masterId = 'master_' + i;
            var statsGroupId = 'stats_group_'+ masterId;
            $('#' + optionsId).append($("<div class='stats-group' />").prop('id', statsGroupId));

            $('#' + statsGroupId)
                .append($("<span class='master' />")
                    .append($("<input type='checkbox' />").prop('id', masterId))
                    .append($("<label for='" + masterId  + "' />").html(group.title)));

            // children
            var childIds = [];
            $(group.functions).each(function(j, fn) {
                var childId = 'child_' + i + '_' + j;
                childIds.push(childId);
                $('#' + statsGroupId)
                    .append($("<span class='child reportVar' />")
                        .append($("<input type='checkbox' />").prop('id', childId).prop('value', fn.id))
                        .append($("<label for='" + childId  + "' />").html(fn.label)));
            });

            // listen for master clicks to check children
            $('#' + masterId).click(function() {
                var checked = $(this).is(':checked');
                $(childIds).each(function(j, childId) {
                    $('#' + childId).prop('checked', checked);
                });
            });

            // listen for children clicks to check master
            $(childIds).each(function(j, childId) {
                // when a child is checked, the master should only be checked if
                // all the other children are also checked.
                $('#' + childId).click(function() {
                    var allChecked = true;
                    $(childIds).each(function(k, childId) {
                        if (!$('#' + childId).is(':checked')) {
                            allChecked = false;
                        }
                    });
                    $('#' + masterId).prop('checked', allChecked);
                });
            });

        });
    };

    /**
     * Submit a request to the server to generate a report.
     */
    var submitReportRequestToServer = function() {
        var data;
        var url = '/districtmapping/plan/' + _options.planId;
        if (_options.calculatorReports.length > 0) {
            data = getCalculatorReportOptions();
            url += '/getcalculatorreport/';
        } else {
            data = getReportOptions();
            url += '/getreport/';
        }

        if (data.functionIds === "") {
            $('<div />').text(gettext('Please select one or more reports to be generated.')).dialog({
                modal: true, autoOpen: true, title: 'Warning', resizable:false
            });
            return;
        }

        var statusDiv = $('<div class="reportStatus" />');
        statusDiv.append('<img class="reportLoading" src="/static/images/loading-large.gif" />');
        statusDiv.append($('<h1 id="genreport" />').text(gettext('Generating Report')));
        statusDiv.append($('<p />').text(gettext('You may use the rest of the application while the report is building.')));
        statusDiv.append($('<p />').text(gettext('A preview of your report will appear in this space when it is ready.')));
        $('#reportPreview').empty();
        $('#reportPreview').append(statusDiv);

        pollCount = 0;
        $.ajax({
            type:'POST',
            url: url,
            data: data,
            success: pollReport,
            error: reportError
        });
    };

    var reportError = function(xhr, txtStatus, msg) {
        if (typeof(msg) == 'undefined') {
            msg = '';
        }
        var statusDiv = $('<div class="reportStatus" />');
        statusDiv.append($('<h1 id="genreport" />').text(gettext('Report Error')));
        statusDiv.append($('<p />').text(gettext('Sorry, this report cannot be previewed.')));
        $('#reportPreview').empty();
        $('#reportPreview').append(statusDiv);
    };

    var pollReport = function(data, textStatus, xhr) {
        if (data.success) {
            $('#reportPreview').append('<!-- ' + (pollCount++) + ' -->');
            var success = null,
                type = null,
                newdata = null;
            if (data.retry !== 0) {
                type = 'POST';
                success = pollReport;
                newdata = { stamp: data.stamp };
                setTimeout(function(){
                    $.ajax({
                        type: type,
                        url: data.url,
                        data: newdata,
                        success: success,
                        error: reportError
                    });
                }, data.retry * 1000);
            }
            else {
                loadPreviewContent(data.url);
            }
        }
        else {
            var statusDiv = $('<div class="reportStatus" />');
            statusDiv.append($('<h1 id="genreport" />').text(gettext('Connection Failed')));
            statusDiv.append($('<p />').text(gettext('There was a problem checking your report status. You can resume checking by clicking on the "Create and Preview Report" button.')));
            $('#reportPreview').empty();
            $('#reportPreview').append(statusDiv);
        }
    };

    /**
     * Get the options set in the UI for this report when calculator reports are configured.
     *
     * Returns:
     *   The report options with properties set to form values.
     */
    var getCalculatorReportOptions = function() {
        var vals = [];
        $('.reportVar').each( function() {
            $this = $(this);
            if ($this.children('input:checked').length > 0) {
                vals.push($this.children('input').val());
            }
        });
        return { functionIds: vals.join(',') };
    };

    /**
     * Get the options set in the UI for this report when BARD reports are configured.
     *
     * Returns:
     *   The report options with properties set to form values.
     */
    var getReportOptions = function() {
        var getConcatenated = function(cls) {
            var value = '';
            $('.' + cls + '.reportVar').each( function() {
                $this = $(this);
                if ($this.children('input:checked').length > 0) {
                    value += $this.children('label').text();
                    value += "|";
                    value += $this.children('input').val();
                    value += '^';
                }
            });
            if (value.length > 0) {
                return value.substring(0, value.length - 1);
            }
        };

        // Get the ratioVar info from any areas such as Majority-Minority
        // Districts or Party-Controlled Districts
        _ratioVars = [];
        $('.ratioVar').each( function(index, element) {
            var name = $(element).val();
            var numerators = getConcatenated(name);
            // If none of the boxes are checked, don't send the ratioVar
            if (numerators) {
                var ratioVar = $('#' + name + 'Denominator').val();
                ratioVar += '||' + $('#' + name + 'Threshold').val();
                ratioVar += '||' + getConcatenated(name);
                ratioVar += '||' + $('label[for^=' + name + ']').text();

                _ratioVars.push(ratioVar);
            }
        });

        _popVar = $('#popVar').val();
        _popVarExtra = getConcatenated('popVarExtra');
        _splitVars = getConcatenated('splitVar');
        _repCompactness = $('#repCompactness').is(':checked');
        _repCompactnessExtra = $('#repCompactnessExtra').is(':checked');
        _repSpatial = $('#repSpatial').is(':checked');
        _repSpatialExtra = $('#repSpatialExtra').is(':checked');
        var data = {
            popVar: _popVar,
            popVarExtra: _popVarExtra,
            ratioVars: _ratioVars,
            splitVars: _splitVars,
            repCompactness: _repCompactness,
            repCompactnessExtra: _repCompactnessExtra,
            repSpatial: _repSpatial,
            repSpatialExtra: _repSpatialExtra
        };

        return data;
    };

    /**
     * Load the report's content as a preview. This is a callback function
     * that is triggered when a report is generated successfully.
     *
     * Parameters:
     *   data -- The JSON server response.
     *   textStatus -- The text status of the HTTP ajax call.
     *   xhr -- The XmlHTTPRequest object.
     */
    var loadPreviewContent = function(url) {
        if (typeof(_gaq) != 'undefined') { _gaq.push(['_trackEvent', 'Reports', 'RanReport']); }
        _options.previewContainer.load(url, function(){

            var resultsAmt = _options.previewContainer.find(".report_panel").length;
            var $resultsPanels = _options.previewContainer.find(".report_panel");

            //build tab structure from report response, necessary for jqueryUI
            var $tabNav = $('<ul/>', {id: 'stats-tab-nav'});
            var $tabNextButton = $('<input/>', {'type': 'radio', 'id': 'stats-tab-next'});
            var $tabNextLabel = $('<label/>', {'for': 'stats-tab-next', 'html': 'Next'});
            var $tabPrevButton = $('<input/>', {'type': 'radio', 'id': 'stats-tab-prev'});
            var $tabPrevLabel = $('<label/>', {'for': 'stats-tab-prev', 'html': 'Prev'});

            var $tabNavButtons = $('<div/>', {'class': 'stats-nav-buttons'});
                $tabNavButtons.append($tabPrevButton, $tabPrevLabel ,$tabNextButton, $tabNextLabel);
                $tabNavButtons.buttonset();

            $resultsPanels.each(function(){
                var $tabNavItem = $('<a/>', {html: $(this).find('.report_panel_title').html(), href: '#'+ $(this).attr('id')});
                $tabNav.append($('<li/>', {html: $tabNavItem }));
            });

            //add nav buttons
            if (resultsAmt > 1) {
                $(this).prepend($tabNavButtons);
            }

            //prepend tab nav
            _options.previewContainer.prepend($tabNav);
            //destroy previous tab init, check for existance for IE7
            if (_options.previewContainer.data('tabs') !== undefined) {
                _options.previewContainer.tabs("destroy");
            }
            //init tab scrip
            _options.previewContainer.tabs();

            //nav button tab switching behaviors
            $('#stats-tab-next').click(function() {
                var $tabs = _options.previewContainer.tabs();
                var selected = $tabs.tabs('option', 'selected');
                if (selected + 1 == resultsAmt) {
                    $tabs.tabs('select', 0);
                } else {
                    $tabs.tabs('select', selected + 1);
                }
            });
            $('#stats-tab-prev').click(function() {
                var $tabs = _options.previewContainer.tabs();
                var selected = $tabs.tabs('option', 'selected');
                if (selected === 0) {
                    $tabs.tabs('select', resultsAmt - 1);
                } else {
                    $tabs.tabs('select', selected - 1);
                }
            });
        });

        var link = window.location.protocol + '//' + window.location.host + url;
        var $btnOpenReport = $('<a href="' + link + '" target="report" />');
        $btnOpenReport.append($('<button id="btnOpenReport" />').
            text(gettext('Open Current Report in New Window')));
        $('#reportButtons #btnOpenReport').remove();
        $('#reportButtons').append($btnOpenReport);
        $('button', $btnOpenReport).button();

        setTimeout(function() {
            // do some formatting
            $('#reportPreview td.cellinside').each( function() {
                $(this).text(addCommas($(this).text()));
            });
        }, 100);
    };

    /**
     * Add commas to unformatted numbers in the reports preview
     * from http://www.mredkj.com/javascript/nfbasic.html
     */
    var addCommas = function(nStr) {
        nStr += '';
        x = nStr.split('.');
        x1 = x[0];
        x2 = x.length > 1 ? '.' + x[1] : '';
        var rgx = /(\d+)(\d{3})/;
        while (rgx.test(x1)) {
            x1 = x1.replace(rgx, '$1' + ',' + '$2');
        }
        return x1 + x2;
    };

    return _self;
};
