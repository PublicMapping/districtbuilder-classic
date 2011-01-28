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
            reportUrl: '',
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
        return _self;
    };
    
    // the working dialog
    var $working = $('<div title="Working">Please wait while your report is created. This will take a few minutes.</div>').dialog({ 
        autoOpen: false,
        escapeOnClose: false,
        modal:true,
        resizable:false,
        open: function(event, ui) { 
            $(".ui-dialog-titlebar-close", $(this).parent()).hide();
        }
    });

    /**
     * Submit a request to the server to generate a report.
     */
    var submitReportRequestToServer = function() {
        $working.dialog('open');
        data = getReportOptions();
        $.post(_options.reportUrl, data, loadPreviewContent);
    };

    /**
     * Get the options set in the UI for this report.
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
        _repCompactness = $('#repCompactness').attr('checked');
        _repCompactnessExtra = $('#repCompactnessExtra').attr('checked');
        _repSpatial = $('#repSpatial').attr('checked');
        _repSpatialExtra = $('#repSpatialExtra').attr('checked');
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
     *   XMLHttpRequest -- The XmlHTTPRequest object.
     */
    var loadPreviewContent = function(data, textStatus, XMLHttpRequest) {
        if (typeof(_gaq) != 'undefined') { _gaq.push(['_trackEvent', 'Reports', 'RanReport']); }
        $working.dialog('close');
        if (data.success) {
            _options.previewContainer.html(data.preview); 
            var link = 'https://' + location.host + data.file
            $btnOpenReport = $('<a href="' + link + '" target="report" ><button id="btnOpenReport">Open report in a new window</button></a>');
            $('#reportButtons #btnOpenReport').remove();
            $('#reportButtons').append($btnOpenReport);  
            $('button', $btnOpenReport).button();

            // do some formatting
            $('#reportPreview td.cellinside').each( function() {
                $(this).text(addCommas($(this).text()));
            });
        } 
        else {
            $('<div title="Report Error">Sorry, we weren\'t able to preview this report; <p>' + data.message + '</p></div>').dialog({ autoOpen:true });
        }
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
